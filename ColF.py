import itertools
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


# ===========================================================================
# Лексический анализ
# ===========================================================================

# Слова-операторы и много символьные стрелки (проверяются до имён переменных)
KEYWORD_OPS = [
    ('<=>', '↔'), ('<->', '↔'),
    ('==>', '→'), ('->', '→'), ('=>', '→'),
    ('xor', '⊕'), ('XOR', '⊕'),
    ('and', '∧'), ('AND', '∧'),
    ('or', '∨'), ('OR', '∨'),
    ('not', '¬'), ('NOT', '¬'),
]

CONSTANT_TOKENS = {
    'true': True, 'True': True, 'истина': True,
    'false': False, 'False': False, 'ложь': False,
}

SIMPLE_OPS = {
    '!': '¬', '~': '¬', '¬': '¬',
    '&': '∧', '*': '∧', '∧': '∧',
    '|': '∨', '+': '∨', '∨': '∨',
    '⊕': '⊕', '≠': '⊕',
    '→': '→', '⇒': '→',
    '↔': '↔', '≡': '↔',
    '(': '(', ')': ')',
}


class ParseError(ValueError):
    """Ошибка разбора выражения с указанием позиции."""

    def __init__(self, message, pos=None):
        self.pos = pos
        if pos is not None:
            message = f"{message} (позиция {pos + 1})"
        super().__init__(message)


def tokenize(text):
    """Разбивает строку на список лексем (kind, value, pos)."""
    tokens = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        # Многосимвольные операторы (стрелки и слова and/or/not/xor)
        matched = False
        for raw, norm in KEYWORD_OPS:
            if text[i:i + len(raw)] == raw:
                end = i + len(raw)
                # слово 'and' не должно быть частью имени переменной (andy)
                if raw[-1].isalpha() and end < n and (text[end].isalnum() or text[end] == '_'):
                    continue
                tokens.append(('op', norm, i))
                i = end
                matched = True
                break
        if matched:
            continue

        # Имена переменных: буква/подчёркивание + буквы/цифры/подчёркивания
        if (ch.isalpha() and ch.isascii()) or ch == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'):
                j += 1
            name = text[i:j]
            if name in CONSTANT_TOKENS:
                tokens.append(('const', CONSTANT_TOKENS[name], i))
            else:
                tokens.append(('var', name, i))
            i = j
            continue

        # Отдельные символы-операторы
        if ch in SIMPLE_OPS:
            tokens.append(('op', SIMPLE_OPS[ch], i))
            i += 1
            continue

        # Цифры: только 0/1 трактуются как константы (последовательность бит)
        if ch.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            num = text[i:j]
            if set(num) <= {'0', '1'}:
                for d in num:
                    tokens.append(('const', d == '1', i))
            else:
                raise ParseError(f"Неизвестный токен '{num}'", i)
            i = j
            continue

        raise ParseError(f"Неизвестный символ '{ch}'", i)
    return tokens


# ===========================================================================
# Синтаксический анализ (рекурсивный спуск)
# AST: ('var', name) | ('const', bool) | ('not', x) | ('bin', op, l, r)
# Приоритет (от низшего к высшему): ↔ , → , ⊕ , ∨ , ∧ , ¬
# ===========================================================================

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def parse(self):
        node = self.parse_equiv()
        if self.i != len(self.tokens):
            tok = self.tokens[self.i]
            raise ParseError(f"Лишний элемент '{tok[1]}'", tok[2])
        return node

    def parse_equiv(self):
        node = self.parse_impl()
        while (t := self.peek()) and t[0] == 'op' and t[1] == '↔':
            self.i += 1
            node = ('bin', '↔', node, self.parse_impl())
        return node

    def parse_impl(self):  # правосторонняя ассоциативность
        node = self.parse_xor()
        t = self.peek()
        if t and t[0] == 'op' and t[1] == '→':
            self.i += 1
            right = self.parse_impl()
            return ('bin', '→', node, right)
        return node

    def parse_xor(self):
        node = self.parse_or()
        while (t := self.peek()) and t[0] == 'op' and t[1] == '⊕':
            self.i += 1
            node = ('bin', '⊕', node, self.parse_or())
        return node

    def parse_or(self):
        node = self.parse_and()
        while (t := self.peek()) and t[0] == 'op' and t[1] == '∨':
            self.i += 1
            node = ('bin', '∨', node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while (t := self.peek()) and t[0] == 'op' and t[1] == '∧':
            self.i += 1
            node = ('bin', '∧', node, self.parse_not())
        return node

    def parse_not(self):
        t = self.peek()
        if t and t[0] == 'op' and t[1] == '¬':
            self.i += 1
            return ('not', self.parse_not())
        return self.parse_atom()

    def parse_atom(self):
        t = self.peek()
        if t is None:
            last = self.tokens[-1][2] if self.tokens else 0
            raise ParseError("Выражение неожиданно завершилось", last)
        if t[0] == 'var':
            self.i += 1
            return ('var', t[1])
        if t[0] == 'const':
            self.i += 1
            return ('const', t[1])
        if t[0] == 'op' and t[1] == '(':
            self.i += 1
            node = self.parse_equiv()
            close = self.peek()
            if close is None or close[1] != ')':
                raise ParseError("Несбалансированные скобки: ожидалась ')'",
                                 close[2] if close else t[2])
            self.i += 1
            return node
        raise ParseError(f"Ожидалось имя переменной, константа или '(' , получено '{t[1]}'", t[2])


def collect_variables(node, acc):
    kind = node[0]
    if kind == 'var':
        acc.add(node[1])
    elif kind == 'not':
        collect_variables(node[1], acc)
    elif kind == 'bin':
        collect_variables(node[2], acc)
        collect_variables(node[3], acc)


def evaluate(node, env):
    kind = node[0]
    if kind == 'var':
        return env[node[1]]
    if kind == 'const':
        return node[1]
    if kind == 'not':
        return not evaluate(node[1], env)
    op, left_node, right_node = node[1], node[2], node[3]
    if op == '∧':
        return evaluate(left_node, env) and evaluate(right_node, env)
    if op == '∨':
        return evaluate(left_node, env) or evaluate(right_node, env)
    if op == '⊕':
        return evaluate(left_node, env) != evaluate(right_node, env)
    if op == '→':
        return (not evaluate(left_node, env)) or evaluate(right_node, env)
    if op == '↔':
        return evaluate(left_node, env) == evaluate(right_node, env)
    raise ParseError(f"Неизвестный оператор '{op}'")


# ===========================================================================
# Логическая функция: таблица истинности, СДНФ/СКНФ, минимизация
# ===========================================================================

class LogicFunction:
    MAX_VARIABLES = 12

    def __init__(self, expression):
        self.original_expression = expression.strip()
        tokens = tokenize(self.original_expression)
        if not tokens:
            raise ParseError("Пустое выражение")
        self.ast = Parser(tokens).parse()

        variables = set()
        collect_variables(self.ast, variables)
        self.variables = sorted(variables)

        if len(self.variables) > self.MAX_VARIABLES:
            raise ValueError(
                f"Слишком много переменных ({len(self.variables)}). "
                f"Максимум {self.MAX_VARIABLES}: таблица истинности заняла бы "
                f"более {2 ** self.MAX_VARIABLES} строк."
            )

        self.truth_table = []
        self.minterms = []   # списки битов (0/1) в порядке self.variables
        self.maxterms = []
        self._table_built = False

    # ------------------------------------------------------------------
    def build_truth_table(self):
        if self._table_built:
            return self.truth_table
        n = len(self.variables)
        self.truth_table, self.minterms, self.maxterms = [], [], []
        for values in itertools.product([0, 1], repeat=n):
            env = dict(zip(self.variables, map(bool, values)))
            result = 1 if evaluate(self.ast, env) else 0
            row = dict(zip(self.variables, values))
            row['result'] = result
            self.truth_table.append(row)
            (self.minterms if result else self.maxterms).append(list(values))
        self._table_built = True
        return self.truth_table

    # ------------------------------------------------------------------
    @staticmethod
    def _bits_to_index(bits):
        idx = 0
        for b in bits:
            idx = (idx << 1) | int(b)
        return idx

    # ------------------------------------------------------------------
    def get_truth_table_text(self):
        self.build_truth_table()
        rows = self.truth_table
        if not rows:
            val = self.get_sdnf()
            return f"Переменных нет — выражение является константой: F ≡ {val}"
        headers = self.variables + ['F']
        widths = [max(len(h), 3) for h in headers]
        sep = '-+-'.join('-' * w for w in widths)
        lines = [sep,
                 ' | '.join(h.ljust(w) for h, w in zip(headers, widths)),
                 sep]
        for row in rows:
            cells = [str(row[v]).ljust(w) for v, w in zip(self.variables, widths)]
            cells.append(str(row['result']).ljust(widths[-1]))
            lines.append(' | '.join(cells))
        lines.append(sep)
        ones = sum(r['result'] for r in rows)
        one_idx = ', '.join(str(i) for i, r in enumerate(rows) if r['result']) or '—'
        lines.append(f"Единиц: {ones} из {len(rows)}   (номера наборов с F=1: {one_idx})")
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    def get_sdnf(self):
        self.build_truth_table()
        if not self.minterms:
            return '0'
        if not self.maxterms:
            return '1'
        terms = []
        for bits in self.minterms:
            parts = [var if val == 1 else f"¬{var}"
                     for var, val in zip(self.variables, bits)]
            terms.append('(' + ' & '.join(parts) + ')')
        return ' ∨ '.join(terms)

    def get_sknf(self):
        self.build_truth_table()
        if not self.maxterms:
            return '1'
        if not self.minterms:
            return '0'
        clauses = []
        for bits in self.maxterms:
            parts = [var if val == 0 else f"¬{var}"
                     for var, val in zip(self.variables, bits)]
            clauses.append('(' + ' ∨ '.join(parts) + ')')
        return ' ∧ '.join(clauses)

    # ------------------------------------------------------------------
    # Квинн–Мак-Класки + выбор существенных импликант + метод Петрика
    # ------------------------------------------------------------------
    def prime_implicants(self):
        """Возвращает (primes, minterm_indices).
        primes: список ((mask, pattern), covered_set), где mask — битовая
        маска значащих разрядов, pattern — их значения (старший разряд =
        первая переменная)."""
        self.build_truth_table()
        minterm_indices = [self._bits_to_index(b) for b in self.minterms]
        # терм хранится как (mask, pattern): бит mask=1 означает, что переменная
        # в конъюнкции НЕ участвует ('-'), pattern задаёт значения значащих
        # разрядов (старший разряд = первая переменная).
        n = len(self.variables)
        full = (1 << n) - 1

        def ones_count(x):
            c = 0
            while x:
                x &= x - 1
                c += 1
            return c

        current = {(full, m): {m} for m in minterm_indices}
        primes = {}
        while current:
            next_level = {}
            used = set()
            keys = list(current.keys())
            for a in range(len(keys)):
                mask_a, pat_a = keys[a]
                for b in range(a + 1, len(keys)):
                    mask_b, pat_b = keys[b]
                    if mask_a != mask_b:
                        continue
                    diff = pat_a ^ pat_b
                    if diff == 0 or ones_count(diff) != 1:
                        continue
                    new_mask = mask_a & ~diff   # differing bit становится '-'
                    new_pattern = pat_a & new_mask
                    key = (new_mask, new_pattern)
                    merged = next_level.setdefault(key, set())
                    merged |= current[keys[a]] | current[keys[b]]
                    used.add(keys[a])
                    used.add(keys[b])
            for key, covered in current.items():
                if key not in used:
                    primes[key] = covered
            current = next_level

        return list(primes.items()), minterm_indices

    def get_min_dnf(self):
        self.build_truth_table()
        if not self.minterms:
            return '0\n  (функция тождественно ложна)'
        if not self.maxterms:
            return '1\n  (функция тождественно истинна)'

        primes, minterm_indices = self.prime_implicants()
        mset = set(minterm_indices)
        cover_sets = [frozenset(covered & mset) for (_key, covered) in primes]

        # --- существенные импликанты ---
        essential = set()
        covered_by_essential = set()
        for idx in minterm_indices:
            holders = [i for i, cs in enumerate(cover_sets) if idx in cs]
            if len(holders) == 1:
                e = holders[0]
                if e not in essential:
                    essential.add(e)
                    covered_by_essential |= cover_sets[e]

        remaining = [i for i in range(len(cover_sets)) if i not in essential]
        uncovered = mset - covered_by_essential
        chosen = set(essential)

        if uncovered:
            # --- метод Петрика для циклического остатка ---
            products = []
            for idx in sorted(uncovered):
                clause = tuple(sorted(i for i in remaining if idx in cover_sets[i]))
                if clause:
                    products.append([clause])

            candidates = list(products[0]) if products else []
            for prod in products[1:]:
                merged_all = {frozenset(c) | frozenset(q)
                              for c in candidates for q in prod}
                uniq = sorted(merged_all, key=len)
                minimal = []
                for s in uniq:  # убираем поглощённые супермножества
                    if not any(m <= s and m != s for m in minimal):
                        minimal.append(s)
                candidates = minimal

            def literal_count(term_idx):
                mask, _pattern = primes[term_idx][0]
                return bin(mask).count('1')

            best, best_cost = None, None
            for sol in candidates:
                cost = sum(literal_count(i) for i in sol)
                if best_cost is None or cost < best_cost:
                    best_cost, best = cost, sol
            if best is not None:
                chosen.update(best)

        # --- сборка текста ДНФ ---
        terms = []
        for i in sorted(chosen):
            mask, pattern = primes[i][0]
            parts = []
            for k, var in enumerate(self.variables):
                bit_pos = len(self.variables) - 1 - k
                if mask & (1 << bit_pos):
                    parts.append(var if (pattern >> bit_pos) & 1 else f"¬{var}")
            terms.append((' & '.join(parts) if parts else '1', len(parts), pattern))
        terms.sort(key=lambda t: (t[1], t[2]))
        dnf = ' ∨ '.join(t[0] for t in terms)
        lits = sum(t[1] for t in terms)
        note = (f"  ({len(terms)} конъюнкций, {lits} литералов; "
                f"покрыто все {len(self.minterms)} единиц таблицы)")
        return dnf + '\n' + note


# ===========================================================================
# Графический интерфейс
# ===========================================================================

BG_MAIN = '#101826'      # тёмно-синий фон окна
BG_PANEL = '#182338'     # панели-секции
BG_FIELD = '#0c1220'     # поля ввода/вывода
FG_MAIN = '#e8eef7'      # основной текст
FG_MUTED = '#8fa3bf'     # приглушённый текст
FG_ACCENT = '#4fc3f7'    # акцент (голубой)
FG_OK = '#81c784'        # зелёный
FG_WARN = '#ffb74d'      # оранжевый
FG_ERR = '#e57373'       # красный
FONT_UI = ('Segoe UI', 10)
FONT_TITLE = ('Segoe UI', 17, 'bold')
FONT_MONO = ('Consolas', 10)


class LogicCalculatorApp:
    def __init__(self, root):
        self.root = root
        root.title('Калькулятор логических функций')
        root.geometry('980x780')
        root.minsize(760, 560)
        root.configure(bg=BG_MAIN)

        style = ttk.Style(root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BG_MAIN, padx=14, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(outer, bg=BG_MAIN)
        header.pack(fill=tk.X)
        tk.Label(header, text='⚡ Калькулятор логических функций',
                 font=FONT_TITLE, fg=FG_ACCENT, bg=BG_MAIN).pack(side=tk.LEFT)
        tk.Label(header, text='Таблица истинности · СДНФ · СКНФ · Мин. ДНФ',
                 font=('Segoe UI', 9), fg=FG_MUTED, bg=BG_MAIN).pack(side=tk.RIGHT)

        # --- панель ввода ---
        input_panel = tk.LabelFrame(outer, text=' Выражение ',
                                    font=FONT_UI, fg=FG_MAIN, bg=BG_PANEL,
                                    bd=1, relief=tk.SOLID, padx=10, pady=8)
        input_panel.pack(fill=tk.X, pady=(12, 8))

        row = tk.Frame(input_panel, bg=BG_PANEL)
        row.pack(fill=tk.X)
        self.expression_var = tk.StringVar(value='(¬A ∨ B) ∧ (A → ¬C)')
        entry = tk.Entry(row, textvariable=self.expression_var,
                         font=('Consolas', 12), bg=BG_FIELD, fg=FG_MAIN,
                         insertbackground=FG_ACCENT, relief=tk.FLAT,
                         highlightthickness=1, highlightbackground='#2c3e5c',
                         highlightcolor=FG_ACCENT)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        entry.bind('<Return>', lambda e: self.calculate())

        tk.Button(row, text='  Рассчитать  ', command=self.calculate,
                  font=('Segoe UI', 10, 'bold'), bg=FG_ACCENT, fg='#06283d',
                  activebackground='#81d4fa', activeforeground='#06283d',
                  relief=tk.FLAT, cursor='hand2', bd=0, padx=8, pady=3
                  ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(row, text=' Примеры ▾', command=self._show_examples,
                  font=FONT_UI, bg='#243450', fg=FG_MAIN,
                  activebackground='#2f4468', activeforeground=FG_MAIN,
                  relief=tk.FLAT, cursor='hand2', bd=0, padx=8, pady=3
                  ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(input_panel,
                 text=('Операторы:  НЕ: ! ~ ¬ not   И: & * ∧ and   ИЛИ: | + ∨ or   '
                       'ИСКЛ.ИЛИ: ⊕ xor   IMPL: -> => →   EQUIV: <-> <=> ≡ ↔   '
                       'скобки ( )   константы: 0 1 true false'),
                 font=('Segoe UI', 8), fg=FG_MUTED, bg=BG_PANEL,
                 anchor='w', justify=tk.LEFT).pack(fill=tk.X, pady=(6, 0))

        # --- панель результатов ---
        result_panel = tk.LabelFrame(outer, text=' Результаты ',
                                     font=FONT_UI, fg=FG_MAIN, bg=BG_PANEL,
                                     bd=1, relief=tk.SOLID, padx=6, pady=6)
        result_panel.pack(fill=tk.BOTH, expand=True)

        self.result_text = scrolledtext.ScrolledText(
            result_panel, wrap=tk.NONE, font=FONT_MONO,
            bg=BG_FIELD, fg=FG_MAIN, relief=tk.FLAT,
            insertbackground=FG_MAIN, selectbackground='#2f4468',
            highlightthickness=1, highlightbackground='#2c3e5c',
            highlightcolor=FG_ACCENT, padx=10, pady=8)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.tag_configure('section', foreground=FG_ACCENT,
                                       font=('Consolas', 10, 'bold'))
        self.result_text.tag_configure('ok', foreground=FG_OK)
        self.result_text.tag_configure('warn', foreground=FG_WARN)
        self.result_text.tag_configure('err', foreground=FG_ERR,
                                       font=('Consolas', 10, 'bold'))
        self.result_text.configure(state=tk.DISABLED)

        # --- статус ---
        self.status_var = tk.StringVar(value='Готов. Введите выражение и нажмите Enter.')
        tk.Label(outer, textvariable=self.status_var, anchor='w',
                 font=('Segoe UI', 9), fg=FG_MUTED, bg='#0b111d',
                 relief=tk.SUNKEN, bd=1, padx=8, pady=3).pack(fill=tk.X, pady=(8, 0))

    # ------------------------------------------------------------------
    def _show_examples(self):
        win = tk.Toplevel(self.root)
        win.title('Примеры выражений')
        win.configure(bg=BG_PANEL, padx=10, pady=10)
        examples = [
            '(¬A ∨ B) ∧ (A → ¬C)',
            'x -> y',
            'a <-> b',
            '(a & b) -> c',
            '!(z & y) ∨ (x ⊕ z)',
            'not (x or y) and z',
            'a ⊕ b ⊕ c',
            'x1 & x2 | !x1 & x3',
            '0',
            '1',
        ]
        tk.Label(win, text='Кликните пример, чтобы подставить его и рассчитать:',
                 font=FONT_UI, fg=FG_MAIN, bg=BG_PANEL).pack(anchor='w')
        for ex in examples:
            b = tk.Button(win, text=ex, anchor='w', justify=tk.LEFT,
                          font=('Consolas', 10), bg=BG_FIELD, fg=FG_ACCENT,
                          activebackground='#2f4468', activeforeground=FG_MAIN,
                          relief=tk.FLAT, cursor='hand2', bd=0, padx=8, pady=4)
            b.pack(fill=tk.X, pady=2)
            b.configure(command=lambda t=ex: (self.expression_var.set(t),
                                              win.destroy(),
                                              self.calculate()))

    # ------------------------------------------------------------------
    def _write(self, text, tags=()):
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.insert(tk.END, text + '\n', tags)
        self.result_text.configure(state=tk.DISABLED)

    def calculate(self):
        expression = self.expression_var.get().strip()
        if not expression:
            messagebox.showwarning('Пусто', 'Введите логическое выражение.')
            return

        self.status_var.set('Вычисление…')
        self.root.update_idletasks()

        try:
            lf = LogicFunction(expression)
        except ParseError as e:
            self._render_error(expression, str(e))
            return
        except Exception as e:  # noqa: BLE001
            self._render_error(expression, f'{type(e).__name__}: {e}')
            return

        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self.result_text.configure(state=tk.DISABLED)

        self._write(f'Исходное выражение:  {lf.original_expression}', ('section',))
        vars_line = ', '.join(lf.variables) if lf.variables else '— (нет переменных)'
        self._write(f'Переменные ({len(lf.variables)}):  {vars_line}\n')

        lf.build_truth_table()
        self._write('┌─ Таблица истинности ─────────────────────────────', ('section',))
        if lf.truth_table:
            self._write(lf.get_truth_table_text(), ('ok',))
        else:
            self._write(f'Выражение — константа: F ≡ {lf.get_sdnf()}', ('warn',))

        self._write('\n┌─ СДНФ (совершенная дизъюнктивная нормальная форма)', ('section',))
        self._write(lf.get_sdnf())

        self._write('\n┌─ СКНФ (совершенная конъюнктивная нормальная форма)', ('section',))
        self._write(lf.get_sknf())

        self._write('\n┌─ Минимальная ДНФ (Квинн–Мак-Класки + Петрик)', ('section',))
        self._write(lf.get_min_dnf(), ('ok',))

        self.status_var.set(f'Готово: переменных {len(lf.variables)}, '
                            f'наборов {len(lf.truth_table)}.')

    def _render_error(self, expression, message):
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self._write(f'Исходное выражение:  {expression}', ('section',))
        self._write('✖ Не удалось разобрать выражение', ('err',))
        self._write(message, ('err',))
        if 'позиция' in message:
            try:
                pos = int(message.rsplit('позиция', 1)[1].strip(' ()')) - 1
                if 0 <= pos < len(expression):
                    marked = expression[:pos] + '▸' + expression[pos:]
                    self._write(f'    {marked}', ('warn',))
            except ValueError:
                pass
        self._write('\nПодсказка: проверьте скобки и операторы.\n'
                    'Примеры корректных записей:  (a & b) -> c ;  ¬x ∨ y ;  a ⊕ b ⊕ c',
                    ('warn',))
        self.result_text.configure(state=tk.DISABLED)
        self.status_var.set('Ошибка разбора выражения')


def main():
    root = tk.Tk()
    app = LogicCalculatorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
