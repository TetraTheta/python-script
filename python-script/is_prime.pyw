import sys
import tkinter.messagebox as msgbox


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True


##########
#  MAIN  #
##########
def main():
    if len(sys.argv) < 2:
        msgbox.showerror("Input Error", "Please provide a valid integer as a command-line argument.")
        sys.exit(1)

    try:
        number = int(sys.argv[1])  # Convert the input to an integer
    except ValueError:
        msgbox.showerror("Type Error", "Argument must be an integer.")
        sys.exit(1)

    if is_prime(number):
        msgbox.showinfo("YES", f"{number} is a Prime Number")
    else:
        msgbox.showwarning("NO", f"{number} is NOT a Prime Number")


if __name__ == "__main__":
    main()
