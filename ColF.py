import itertools
from collections import defaultdict
import re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


class LogicFunction:
    def __init__(self, variables=None, function=None, expression=None):
        """Инициализация логической функции"""
        if expression is not None:
            self.parse_expression(expression)
        else:
            self.variables = variables
            self.function = function

        self.truth_table = []
        self.minterms = []
        self.maxterms = []

    def parse_expression(self, expression):
        """Парсинг логического выражения из строки"""
        self.original_expression = expression

        variables = sorted(list(set(re.findall(r'[a-zA-Z]', self.original_expression))))
        self.variables = variables

        py_expr = self.convert_to_python(expression)

        func_str = f"lambda {', '.join(variables)}: {py_expr}"
        try:
            self.function = eval(func_str)
        except Exception as e:
            raise ValueError(f"Ошибка создания функции: {e}")

    def convert_to_python(self, expr):
        """Преобразование логического выражения в Python выражение"""
        # Удаляем пробелы
        expr = expr.replace(' ', '')

        # Заменяем операторы на временные метки для удобства парсинга
        expr = (expr.replace('->', '→')
                .replace('=>', '→')
                .replace('<->', '↔')
                .replace('<=>', '↔')
                .replace('¬', '!')
                .replace('~', '!')
                .replace('&', '∧')
                .replace('*', '∧')
                .replace('|', '∨')
                .replace('+', '∨'))

        # Обрабатываем выражение рекурсивно
        return self.parse_recursive(expr)

    def parse_recursive(self, expr):
        """Рекурсивный парсинг выражения"""
        if not expr:
            return ""

        # Убираем внешние скобки
        expr = self.strip_outer_parentheses(expr)

        # Находим оператор с наименьшим приоритетом
        pos = self.find_operator_position(expr)

        if pos != -1:
            operator = expr[pos]
            left = expr[:pos]
            right = expr[pos + 1:]

            if operator == '→':  # Импликация
                left_parsed = self.parse_recursive(left)
                right_parsed = self.parse_recursive(right)
                return f"(not ({left_parsed}) or ({right_parsed}))"

            elif operator == '↔':  # Эквивалентность
                left_parsed = self.parse_recursive(left)
                right_parsed = self.parse_recursive(right)
                return f"(({left_parsed}) and ({right_parsed})) or (not ({left_parsed}) and not ({right_parsed}))"

            elif operator == '∨':  # OR
                left_parsed = self.parse_recursive(left)
                right_parsed = self.parse_recursive(right)
                return f"(({left_parsed}) or ({right_parsed}))"

            elif operator == '∧':  # AND
                left_parsed = self.parse_recursive(left)
                right_parsed = self.parse_recursive(right)
                return f"(({left_parsed}) and ({right_parsed}))"

            elif operator == '⊕':  # XOR
                left_parsed = self.parse_recursive(left)
                right_parsed = self.parse_recursive(right)
                return f"(({left_parsed}) ^ ({right_parsed}))"

        # Обработка отрицания
        if expr.startswith('!'):
            inner = self.parse_recursive(expr[1:])
            return f"not ({inner})"

        if re.match(r'^[a-zA-Z]+$', expr):
            return expr

        if expr.startswith('(') and expr.endswith(')'):
            return self.parse_recursive(expr[1:-1])

        return expr

    def strip_outer_parentheses(self, expr):
        """Удаление внешних парных скобок"""
        if expr.startswith('(') and expr.endswith(')'):
            count = 0
            for i, char in enumerate(expr):
                if char == '(':
                    count += 1
                elif char == ')':
                    count -= 1
                    if count == 0 and i < len(expr) - 1:
                        return expr
            return expr[1:-1]
        return expr

    def find_operator_position(self, expr):
        """Нахождение позиции оператора с наименьшим приоритетом"""
        parentheses_count = 0
        min_priority = float('inf')
        result_pos = -1

        # Приоритет операторов
        priorities = {
            '→': 1,
            '↔': 2,
            '∨': 3,
            '⊕': 4,
            '∧': 5,
        }

        for i, char in enumerate(expr):
            if char == '(':
                parentheses_count += 1
            elif char == ')':
                parentheses_count -= 1
            elif parentheses_count == 0 and char in priorities:
                priority = priorities[char]
                if priority < min_priority:
                    min_priority = priority
                    result_pos = i

        return result_pos

    def build_truth_table(self):
        """Построение таблицы истинности"""
        if not hasattr(self, 'variables') or not self.variables:
            return None

        n = len(self.variables)
        self.truth_table = []
        self.minterms = []
        self.maxterms = []

        # Генерируем все возможные комбинации значений переменных
        for values in itertools.product([0, 1], repeat=n):
            row = dict(zip(self.variables, values))
            try:
                # Преобразуем 0/1 в False/True для вычисления функции
                bool_values = {k: bool(v) for k, v in row.items()}
                result = self.function(**bool_values)
                # Преобразуем результат обратно в 0/1
                result_int = 1 if result else 0
                row['result'] = result_int
                self.truth_table.append(row)

                if result_int == 1:
                    self.minterms.append(values)
                else:
                    self.maxterms.append(values)
            except Exception as e:
                print(f"Ошибка при вычислении функции: {e}")
                return None

        return self.truth_table

    def get_truth_table_text(self):
        """Получение таблицы истинности в виде текста"""
        if not self.truth_table:
            if self.build_truth_table() is None:
                return "Ошибка при построении таблицы истинности"

        text = "Таблица истинности:\n"
        # Заголовок
        header = " | ".join(self.variables) + " | result"
        text += header + "\n"
        text += "-" * len(header) + "\n"

        # Данные
        for row in self.truth_table:
            values = [str(row[var]) for var in self.variables]
            text += " | ".join(values) + f" | {row['result']}\n"

        return text

    def get_sdnf(self):
        """Построение СДНФ (Совершенной дизъюнктивной нормальной формы)"""
        if not self.minterms:
            if self.build_truth_table() is None:
                return "Ошибка"

        if not self.minterms:
            return "0"

        terms = []
        for values in self.minterms:
            term_parts = []
            for var, val in zip(self.variables, values):
                if val == 1:
                    term_parts.append(var)
                else:
                    term_parts.append(f"¬{var}")
            terms.append(" & ".join(term_parts))

        return " | ".join(f"({term})" for term in terms)

    def get_sknf(self):
        """Построение СКНФ (Совершенной конъюнктивной нормальной формы)"""
        if not self.maxterms:
            if self.build_truth_table() is None:
                return "Ошибка"

        if not self.maxterms:
            return "1"  # функция всегда истинна

        terms = []
        for values in self.maxterms:
            term_parts = []
            for var, val in zip(self.variables, values):
                if val == 0:
                    term_parts.append(var)
                else:
                    term_parts.append(f"¬{var}")
            terms.append(" | ".join(term_parts))

        return " & ".join(f"({term})" for term in terms)

    def quine_mccluskey(self):
        """Алгоритм Квайна-Мак-Класки для минимизации ДНФ"""
        if not self.minterms:
            if self.build_truth_table() is None:
                return "Ошибка"

        if not self.minterms:
            return "0"

        # Преобразуем минтермы в бинарные строки в правильном порядке переменных
        minterm_strings = []
        for minterm in self.minterms:
            # Создаем словарь значение-переменная для правильного порядка
            minterm_dict = dict(zip(self.variables, minterm))
            # Формируем строку в правильном порядке переменных
            binary_str = ''.join(str(minterm_dict[var]) for var in self.variables)
            minterm_strings.append(binary_str)

        # Группируем по количеству единиц
        groups = defaultdict(list)
        for minterm in minterm_strings:
            ones = minterm.count('1')
            groups[ones].append((minterm, [int(minterm, 2)]))

        # Функция для сравнения двух термов
        def can_combine(term1, term2):
            diff_count = 0
            result = []
            for a, b in zip(term1[0], term2[0]):
                if a != b:
                    diff_count += 1
                    result.append('-')
                else:
                    result.append(a)
            return diff_count == 1, ''.join(result)

        # Основной цикл алгоритма
        all_prime_implicants = []
        while True:
            new_groups = defaultdict(list)
            used = set()

            for ones in sorted(groups.keys()):
                if ones + 1 in groups:
                    for term1 in groups[ones]:
                        for term2 in groups[ones + 1]:
                            combinable, combined = can_combine(term1, term2)
                            if combinable:
                                new_minterms = sorted(list(set(term1[1] + term2[1])))
                                new_groups[ones].append((combined, new_minterms))
                                used.add(term1[0])
                                used.add(term2[0])

            # Добавляем непокрытые простые импликанты
            for ones in groups:
                for term in groups[ones]:
                    if term[0] not in used:
                        all_prime_implicants.append(term)

            if not new_groups:
                break

            groups = new_groups

        # Добавляем оставшиеся импликанты из последней группы
        for ones in groups:
            for term in groups[ones]:
                all_prime_implicants.append(term)

        # Удаляем дубликаты
        unique_implicants = []
        seen = set()
        for implicant in all_prime_implicants:
            if implicant[0] not in seen:
                unique_implicants.append(implicant)
                seen.add(implicant[0])

        # Преобразуем простые импликанты в читаемый вид с правильным порядком переменных
        minimized_terms = []
        for implicant in unique_implicants:
            term_parts = []
            # Сопоставляем каждый символ импликанта с соответствующей переменной
            for var, char in zip(self.variables, implicant[0]):
                if char == '1':
                    term_parts.append(var)
                elif char == '0':
                    term_parts.append(f"¬{var}")
                # '-' пропускаем (переменная отсутствует в импликанте)
            if term_parts:  # проверка на случай, если все переменные '-'
                minimized_terms.append(" & ".join(term_parts))

        return " | ".join(minimized_terms) if minimized_terms else "1"


class LogicCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Калькулятор логических функций")
        self.root.geometry("900x750")
        self.root.configure(bg='black')

        self.setup_ui()

    def setup_ui(self):
        """Создание интерфейса"""
        # Основной фрейм
        main_frame = tk.Frame(self.root, bg='black', padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        title_label = tk.Label(main_frame,
                               text="Калькулятор логических функций",
                               bg='black',
                               fg='white',
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Инструкция
        instruction_text = (
            "Поддерживаемые операторы:\n"
            "AND: &, *, and\n"
            "OR: |, +, or\n"
            "NOT: !, ¬, ~, not\n"
            "XOR: ⊕\n"
            "Импликация: →, ->, =>\n"
            "Эквивалентность: ↔, <->, <=>\n"
            "Скобки: (, )\n\n"
            "Примеры выражений:\n"
            "x → y, x ↔ y, (x & y) → z\n"
            "!(x & y), ¬(a | b), (!z + y) → (!z ⊕ !x)"
        )
        instruction_label = tk.Label(main_frame,
                                     text=instruction_text,
                                     justify=tk.LEFT,
                                     bg='black',
                                     fg='white',
                                     font=("Arial", 10))
        instruction_label.pack(pady=(0, 10), anchor='w')

        # Фрейм для поля ввода
        input_frame = tk.Frame(main_frame, bg='black')
        input_frame.pack(fill=tk.X, pady=(10, 5))

        # Метка для поля ввода
        input_label = tk.Label(input_frame,
                               text="Введите логическое выражение:",
                               bg='black',
                               fg='white',
                               font=("Arial", 10))
        input_label.pack(anchor='w')

        # Поле ввода выражения
        self.expression_var = tk.StringVar()
        self.expression_entry = tk.Entry(input_frame,
                                         textvariable=self.expression_var,
                                         width=60,
                                         bg='gray20',
                                         fg='white',
                                         insertbackground='white',
                                         font=("Arial", 10))
        self.expression_entry.pack(fill=tk.X, pady=(5, 0))
        self.expression_entry.bind('<Return>', lambda e: self.calculate())

        # Кнопка расчета
        self.calculate_button = tk.Button(main_frame,
                                          text="Рассчитать",
                                          command=self.calculate,
                                          bg='gray30',
                                          fg='white',
                                          font=("Arial", 10),
                                          relief=tk.RAISED,
                                          bd=2)
        self.calculate_button.pack(pady=10)

        # Область вывода результатов
        self.result_text = scrolledtext.ScrolledText(
            main_frame,
            width=90,
            height=30,
            wrap=tk.WORD,
            font=("Courier New", 10),
            bg='black',
            fg='white',
            insertbackground='white',
            selectbackground='gray40'
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Статус бар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = tk.Label(main_frame,
                              textvariable=self.status_var,
                              relief=tk.SUNKEN,
                              bg='gray20',
                              fg='white',
                              font=("Arial", 9))
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def calculate(self):
        """Обработка расчета"""
        expression = self.expression_var.get().strip()

        if not expression:
            messagebox.showwarning("Предупреждение", "Пожалуйста, введите логическое выражение")
            return

        try:
            self.status_var.set("Вычисление...")
            self.root.update()

            # Создаем объект логической функции
            lf = LogicFunction(expression=expression)

            # Формируем результат
            result_text = f"Анализ выражения: {expression}\n"
            result_text += f"Обнаруженные переменные: {', '.join(lf.variables)}\n\n"

            # Таблица истинности
            result_text += lf.get_truth_table_text() + "\n"

            # Различные формы
            result_text += "Совершенная дизъюнктивная нормальная форма (СДНФ):\n"
            result_text += lf.get_sdnf() + "\n\n"

            result_text += "Совершенная конъюнктивная нормальная форма (СКНФ):\n"
            result_text += lf.get_sknf() + "\n\n"

            result_text += "Минимальная ДНФ:\n"
            result_text += lf.quine_mccluskey() + "\n"

            # Выводим результат
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, result_text)

            self.status_var.set("Расчет завершен успешно")

        except Exception as e:
            error_msg = f"Ошибка: {str(e)}\nПроверьте правильность введенного выражения"
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, error_msg)
            self.status_var.set("Ошибка при расчете")
            messagebox.showerror("Ошибка", f"Не удалось обработать выражение:\n{str(e)}")


def main():
    root = tk.Tk()
    app = LogicCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
