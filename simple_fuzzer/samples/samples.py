import math
from html.parser import HTMLParser


def sample1(s: str):
    number = float(s)
    r1 = 1 - number
    r2 = r1 / number
    if r1 == r2:
        sample1(str(r2 + 1))
    elif r1 < r2:
        temp = s[(int(r2)) % 10].join(str(r1))
    else:
        temp = s[(int(r1)) % 10].join(str(r2))


def sample2(s: str):
    temp = """%d. {Key} is """
    r = s.split(".")
    temp += r[1]
    temp = temp.format(Key=r[0])
    temp = temp % len(s)

    def can_convert_to_int(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    if can_convert_to_int(r[0]):
        temp += str(math.sqrt(int(r[0])))


def sample3(s: str):
    if s[0] == 'F':
        if s[1] == 'D':
            if s[2] == 'U':
                t = (ord(s[4]) - 65) / (ord(s[3]) - 80)
                if t != 0:
                    index = s.index("L")
                    assert s[index + 1] == 'A'
                    if not s[index + 2:].startswith('B'):
                        raise RuntimeError


def sample4(s: str):
    parser = HTMLParser()
    parser.feed(s)


def sample5(s: str):
    """Evaluates arithmetic expressions with +, -, *, /, (), and **.
    Uses recursive descent with operator precedence. Finds division-by-zero,
    overflow, and syntax errors."""
    s = s.replace(' ', '')
    pos = [0]

    def peek():
        return s[pos[0]] if pos[0] < len(s) else ''

    def consume():
        ch = s[pos[0]]
        pos[0] += 1
        return ch

    def parse_expr():
        left = parse_term()
        while peek() and peek() in '+-':
            op = consume()
            right = parse_term()
            if op == '+':
                left += right
            else:
                left -= right
        return left

    def parse_term():
        left = parse_power()
        while peek() and peek() in '*/':
            op = consume()
            right = parse_power()
            if op == '*':
                left *= right
            elif right == 0:
                raise ZeroDivisionError("Division by zero")
            else:
                left /= right
        return left

    def parse_power():
        left = parse_atom()
        if peek() == '*' and pos[0] + 1 < len(s) and s[pos[0] + 1] == '*':
            consume(); consume()  # skip '**'
            right = parse_power()  # right-associative
            return left ** right
        return left

    def parse_atom():
        if peek() == '(':
            consume()
            val = parse_expr()
            if peek() != ')':
                raise ValueError("Missing ')'")
            consume()
            return val
        elif peek() == '-':
            consume()
            return -parse_atom()
        else:
            start = pos[0]
            while peek().isdigit() or peek() == '.':
                consume()
            if pos[0] == start:
                raise ValueError(f"Expected number at position {pos[0]}")
            return float(s[start:pos[0]])

    result = parse_expr()
    if pos[0] < len(s):
        raise ValueError(f"Unexpected character: {s[pos[0]]!r}")
    return result

def sample6(s: str):
    """A Brainfuck interpreter — a simple 8-instruction Turing-complete language.
    Byte-level mutations naturally produce valid BF programs, and infinite loops
    must be detected."""
    MAX_STEPS = 10000
    tape = [0] * 30000
    ptr = 0
    pc = 0
    steps = 0
    output = []

    # Pre-parse matching brackets (O(n) scan)
    jump_forward = {}
    jump_back = {}
    stack = []
    for i, ch in enumerate(s):
        if ch == '[':
            stack.append(i)
        elif ch == ']':
            if not stack:
                raise ValueError(f"Unmatched ']' at position {i}")
            j = stack.pop()
            jump_forward[j] = i
            jump_back[i] = j
    if stack:
        raise ValueError(f"Unmatched '[' at position {stack[-1]}")

    while pc < len(s):
        if steps >= MAX_STEPS:
            raise TimeoutError(f"Exceeded {MAX_STEPS} steps (possible infinite loop)")
        steps += 1
        ch = s[pc]
        if ch == '>':
            ptr += 1
            if ptr >= len(tape):
                raise IndexError(f"Tape pointer overflow at {ptr}")
        elif ch == '<':
            ptr -= 1
            if ptr < 0:
                raise IndexError("Tape pointer underflow")
        elif ch == '+':
            tape[ptr] = (tape[ptr] + 1) % 256
        elif ch == '-':
            tape[ptr] = (tape[ptr] - 1) % 256
        elif ch == '.':
            output.append(chr(tape[ptr]))
        elif ch == ',':
            tape[ptr] = 0  # no input stream; reads as 0
        elif ch == '[':
            if tape[ptr] == 0:
                pc = jump_forward[pc]  # jump past matching ']'
        elif ch == ']':
            if tape[ptr] != 0:
                pc = jump_back[pc]  # jump back to matching '['
        pc += 1

    return ''.join(output)
