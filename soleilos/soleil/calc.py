"""Hesap makinesinin hesaplama kısmı: dört işlem, parantez, ondalık.

eval kullanılmıyor; küçük bir ayrıştırıcı ifadeyi kendisi hesaplıyor.
Ekranda × ve ÷ görünür, - hem çıkarma hem eksi işaretidir.
"""

from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation, getcontext

getcontext().prec = 28
MAX_DIGITS = 12


class CalcError(Exception):
    pass


def _tokens(expr: str) -> list[str]:
    out, num = [], ""
    for ch in expr:
        if ch.isdigit() or ch == ".":
            num += ch
            continue
        if num:
            out.append(num)
            num = ""
        if ch in "+-×÷()":
            out.append(ch)
        elif ch != " ":
            raise CalcError(ch)
    if num:
        out.append(num)
    return out


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expr(self) -> Decimal:
        value = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            right = self.term()
            value = value + right if op == "+" else value - right
        return value

    def term(self) -> Decimal:
        value = self.factor()
        while self.peek() in ("×", "÷"):
            op = self.take()
            right = self.factor()
            if op == "×":
                value *= right
            else:
                if right == 0:
                    raise CalcError("sıfıra bölme")
                value /= right
        return value

    def factor(self) -> Decimal:
        tok = self.take()
        if tok == "-":
            return -self.factor()
        if tok == "+":
            return self.factor()
        if tok == "(":
            value = self.expr()
            if self.peek() == ")":     # kapanmamış parantez sonda kapanmış sayılır
                self.take()
            return value
        if tok is None or tok in "+-×÷)":
            raise CalcError("eksik sayı")
        try:
            return Decimal(tok)
        except InvalidOperation:
            raise CalcError(tok)


def evaluate(expr: str) -> Decimal:
    tokens = _tokens(expr)
    if not tokens:
        raise CalcError("boş")
    parser = _Parser(tokens)
    try:
        value = parser.expr()
    except (DivisionByZero, InvalidOperation):
        raise CalcError("geçersiz")
    if parser.peek() is not None:
        raise CalcError("fazla")
    return value


def format_number(value: Decimal) -> str:
    """Ekrana sığacak biçim: gereksiz sıfırlar atılır, çok büyük ya da çok
    küçük sayılar bilimsel gösterimle (1.2E+15)."""
    if value == 0:
        return "0"
    text = f"{value.normalize():f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    digits = len(text.replace("-", "").replace(".", ""))
    if digits <= MAX_DIGITS:
        return text
    whole = len(text.replace("-", "").split(".")[0])
    if whole <= MAX_DIGITS:
        return f"{round(value, MAX_DIGITS - whole):f}".rstrip("0").rstrip(".")
    return f"{value:.6E}".replace("E+", "E")


def preview(expr: str) -> str:
    """Yazarken altta görünen sonuç; hesaplanamıyorsa boş."""
    try:
        return format_number(evaluate(expr))
    except CalcError:
        return ""
