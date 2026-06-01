#!/usr/bin/env python3
"""주어진 정수가 소수인지 아닌지 판별한다"""

import tkinter.messagebox as msgbox
from argparse import ArgumentParser


def parse_args() -> int:
    parser = ArgumentParser(description="Check if the given integer is prime.")
    parser.add_argument("number", type=int, help="Integer to test")
    return parser.parse_args().number


def main() -> None:
    try:
        number = parse_args()
    except SystemExit:
        msgbox.showerror("Input Error", "Please provide a valid integer as a command-line argument.")
        raise

    is_prime = number >= 2
    # 제곱근까지만 나눠 보면 합성수 여부를 충분히 판별할 수 있음
    for divisor in range(2, int(number**0.5) + 1):
        if number % divisor == 0:
            is_prime = False
            break

    if is_prime:
        msgbox.showinfo("YES", f"{number} is a Prime Number")
    else:
        msgbox.showwarning("NO", f"{number} is NOT a Prime Number")


if __name__ == "__main__":
    main()
