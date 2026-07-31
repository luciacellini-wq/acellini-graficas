#!/usr/bin/env python3
"""
Compilador SCSS minimo (subset) para el proyecto Augusto Cellini.
Soporta: variables ($var), @import de partials, nesting con '&',
@mixin / @include (con argumentos y valores por defecto), @extend,
y bloques @media anidados. Pensado para compilar sass/main.scss -> css/main.css
sin depender de paquetes externos (no hay acceso a npm/pip en este entorno).

Uso: python3 compile_scss.py <entrada.scss> <salida.css>
"""
import re
import sys
import os

# ---------------------------------------------------------------------------
# 1) Resolver @import (inclusion textual recursiva de partials)
# ---------------------------------------------------------------------------

def strip_comments(text):
    # Bloques /* ... */
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    # Comentarios de linea //  (evitamos romper protocolos tipo https://)
    lines = text.split('\n')
    out = []
    for line in lines:
        line = re.sub(r'(?<!:)//.*$', '', line)
        out.append(line)
    return '\n'.join(out)


def resolve_imports(path, seen=None):
    if seen is None:
        seen = set()
    path = os.path.abspath(path)
    if path in seen:
        return ''
    seen.add(path)
    base_dir = os.path.dirname(path)
    with open(path, encoding='utf-8') as f:
        text = f.read()
    text = strip_comments(text)

    def repl(match):
        name = match.group(1).strip().strip('"\'')
        candidates = []
        if name.endswith('.scss'):
            candidates.append(name)
        else:
            folder, fname = os.path.split(name)
            candidates.append(os.path.join(folder, '_' + fname + '.scss'))
            candidates.append(os.path.join(folder, fname + '.scss'))
        for cand in candidates:
            full = os.path.join(base_dir, cand)
            if os.path.isfile(full):
                return resolve_imports(full, seen)
        raise FileNotFoundError('No se encontro el partial importado: %s (desde %s)' % (name, path))

    text = re.sub(r'@import\s+["\']([^"\']+)["\']\s*;', repl, text)
    return text


# ---------------------------------------------------------------------------
# 2) Variables ($nombre: valor;)
# ---------------------------------------------------------------------------

VAR_DEF_RE = re.compile(r'^\s*(\$[a-zA-Z0-9_-]+)\s*:\s*([^;]+);\s*$', re.M)


def extract_variables(text):
    variables = {}

    def collect(match):
        name, value = match.group(1), match.group(2).strip()
        # sustituir variables ya conocidas dentro del propio valor
        for vname, vval in variables.items():
            value = re.sub(re.escape(vname) + r'(?![\w-])', vval, value)
        variables[name] = value
        return ''  # se elimina la declaracion del texto

    # Solo se consideran declaraciones de variable a nivel de linea completa
    text = VAR_DEF_RE.sub(collect, text)
    return text, variables


def substitute_variables(text, variables):
    # orden por longitud descendente para evitar reemplazos parciales ($a vs $ab)
    for name in sorted(variables, key=len, reverse=True):
        text = re.sub(re.escape(name) + r'(?![\w-])', variables[name], text)
    return text


# ---------------------------------------------------------------------------
# 3) Mixins (@mixin / @include) con soporte de argumentos y defaults
# ---------------------------------------------------------------------------

def find_balanced_block(text, start):
    """Dado un indice donde arranca un bloque en '{', devuelve (contenido, fin)."""
    assert text[start] == '{'
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    raise SyntaxError('Llave sin cerrar en la posicion %d' % start)


def extract_mixins(text):
    mixins = {}
    pattern = re.compile(r'@mixin\s+([a-zA-Z0-9_-]+)\s*(\(([^)]*)\))?\s*\{')
    out = []
    pos = 0
    while True:
        m = pattern.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        name = m.group(1)
        params_raw = m.group(3) or ''
        params = []
        if params_raw.strip():
            for p in params_raw.split(','):
                p = p.strip()
                if ':' in p:
                    pname, pdefault = p.split(':', 1)
                    params.append((pname.strip(), pdefault.strip()))
                else:
                    params.append((p.strip(), None))
        body, end = find_balanced_block(text, m.end() - 1)
        mixins[name] = (params, body)
        pos = end
    return ''.join(out), mixins


def split_args(args_raw):
    args, depth, cur = [], 0, ''
    for ch in args_raw:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def expand_includes(text, mixins):
    pattern = re.compile(r'@include\s+([a-zA-Z0-9_-]+)\s*(\(([^;]*?)\))?\s*;')

    def repl(match):
        name = match.group(1)
        args_raw = match.group(3) or ''
        raw_args = split_args(args_raw) if args_raw.strip() else []
        if name not in mixins:
            raise KeyError('Mixin no definido: %s' % name)
        params, body = mixins[name]
        param_names = [p[0] for p in params]

        named = {}
        positional = []
        for a in raw_args:
            m = re.match(r'^(\$[a-zA-Z0-9_-]+)\s*:\s*(.+)$', a.strip())
            if m and m.group(1) in param_names:
                named[m.group(1)] = m.group(2).strip()
            else:
                positional.append(a.strip())

        values = {}
        pos_i = 0
        for pname, pdefault in params:
            if pname in named:
                values[pname] = named[pname]
            elif pos_i < len(positional):
                values[pname] = positional[pos_i]
                pos_i += 1
            elif pdefault is not None:
                values[pname] = pdefault
            else:
                values[pname] = ''
        expanded = body
        for pname in sorted(values, key=len, reverse=True):
            expanded = re.sub(re.escape(pname) + r'(?![\w-])', values[pname], expanded)
        return expanded

    prev = None
    # iterar por si un mixin incluye a otro (no se usa en este proyecto, pero por robustez)
    for _ in range(5):
        if prev == text:
            break
        prev = text
        text = pattern.sub(repl, text)
    return text


# ---------------------------------------------------------------------------
# 4) Parser de reglas anidadas -> arbol -> lista plana de reglas CSS
# ---------------------------------------------------------------------------

class Rule:
    def __init__(self, selector, media=None):
        self.selector = selector  # None para el nodo raiz
        self.media = media        # condicion de @media si aplica, si no None
        self.decls = []           # lista de strings "prop: value"
        self.children = []        # Rule anidadas
        self.extends = []         # selectores que este bloque extiende


def parse_block(text, pos, end_char_stack=None):
    """Parsea el contenido de un bloque (nivel de una regla) hasta el '}' que
    cierra, devolviendo una lista de items y la posicion final."""
    items = []
    i = pos
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '}':
            return items, i + 1
        # @extend
        m = re.match(r'@extend\s+([^;]+);', text[i:])
        if m:
            items.append(('extend', m.group(1).strip()))
            i += m.end()
            continue
        # bloque @media (u otro @-rule con bloque)
        m = re.match(r'(@media[^{]+)\{', text[i:])
        if m:
            cond = m.group(1).replace('@media', '').strip()
            brace_pos = i + m.end() - 1
            inner, after = find_balanced_block(text, brace_pos)
            sub_items, _ = parse_block(inner, 0)
            items.append(('media', cond, sub_items))
            i = after
            continue
        # buscar el siguiente ';' o '{' que no este dentro de parentesis, lo que aparezca antes
        depth = 0
        j = i
        found = None
        while j < n:
            c = text[j]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == ';' and depth == 0:
                found = (';', j)
                break
            elif c == '{' and depth == 0:
                found = ('{', j)
                break
            elif c == '}' and depth == 0:
                found = ('}', j)
                break
            j += 1
        if not found:
            break
        kind, j = found
        chunk = text[i:j].strip()
        if kind == ';':
            if chunk:
                items.append(('decl', chunk))
            i = j + 1
        elif kind == '{':
            selector = chunk
            inner, after = find_balanced_block(text, j)
            sub_items, _ = parse_block(inner, 0)
            items.append(('rule', selector, sub_items))
            i = after
        else:  # '}'
            return items, j + 1
    return items, i


def combine_selectors(parent, child):
    """parent y child son strings con posibles comas. Devuelve el selector combinado."""
    parents = [p.strip() for p in parent.split(',')] if parent else ['']
    children = [c.strip() for c in child.split(',')]
    out = []
    for p in parents:
        for c in children:
            if '&' in c:
                out.append(c.replace('&', p))
            else:
                out.append((p + ' ' + c).strip() if p else c)
    return ', '.join(out)


def flatten(items, parent_selector, media_ctx, out_rules, extend_registry):
    current_decls = []
    current_extends = []

    def flush():
        if current_decls or current_extends:
            out_rules.append({
                'selector': parent_selector,
                'media': media_ctx,
                'decls': list(current_decls),
            })
            if current_extends:
                for target in current_extends:
                    extend_registry.setdefault(target, []).append(parent_selector)
            current_decls.clear()
            current_extends.clear()

    for item in items:
        if item[0] == 'decl':
            current_decls.append(item[1])
        elif item[0] == 'extend':
            current_extends.append(item[1])
        elif item[0] == 'rule':
            flush()
            _, selector, sub_items = item
            combined = combine_selectors(parent_selector, selector)
            flatten(sub_items, combined, media_ctx, out_rules, extend_registry)
        elif item[0] == 'media':
            flush()
            _, cond, sub_items = item
            new_media = (media_ctx + ' and ' + cond) if media_ctx else cond
            flatten(sub_items, parent_selector, new_media, out_rules, extend_registry)
    flush()


def compile_scss(entry_path):
    text = resolve_imports(entry_path)
    text, variables = extract_variables(text)
    text = substitute_variables(text, variables)
    text, mixins = extract_mixins(text)
    text = expand_includes(text, mixins)

    items, _ = parse_block(text, 0)
    out_rules = []
    extend_registry = {}
    flatten(items, '', None, out_rules, extend_registry)

    # aplicar @extend: agregar selectores que extienden a la regla que matchea el target
    for rule in out_rules:
        sels = [s.strip() for s in rule['selector'].split(',')]
        extra = []
        for s in sels:
            if s in extend_registry:
                extra.extend(extend_registry[s])
        if extra:
            rule['selector'] = rule['selector'] + ', ' + ', '.join(extra)

    # emitir CSS agrupando por contexto de media consecutivo
    lines = []
    lines.append('/* Archivo generado automaticamente por build/compile_scss.py */')
    lines.append('/* No editar a mano: modificar los partials en /sass y volver a compilar. */\n')

    def emit_rule(rule, indent=''):
        if not rule['decls']:
            return
        lines.append('%s%s {' % (indent, rule['selector']))
        for d in rule['decls']:
            lines.append('%s  %s;' % (indent, d))
        lines.append('%s}' % indent)

    i = 0
    while i < len(out_rules):
        rule = out_rules[i]
        if rule['media']:
            media_cond = rule['media']
            lines.append('@media %s {' % media_cond)
            while i < len(out_rules) and out_rules[i]['media'] == media_cond:
                emit_rule(out_rules[i], indent='  ')
                i += 1
            lines.append('}')
        else:
            emit_rule(rule)
            i += 1

    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Uso: python3 compile_scss.py <entrada.scss> <salida.css>')
        sys.exit(1)
    entry, out = sys.argv[1], sys.argv[2]
    css = compile_scss(entry)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(css)
    print('OK -> %s (%d bytes)' % (out, len(css)))
