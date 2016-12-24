choice = None
number = ""

def on_dtmf_digit(digit):
    global choice
    global number

    if choice is None:
        if digit.isdigit():
            num = int(digit)
            if num == 1:
                print('Hexadecimal')
                choice = 1
            elif num == 0:
                print('Binary')
                choice = 0
            else:
                print('{}'.format(num))
                choice = None
    else:
        # Check if we received a '#', if so, we can convert
        if chr(ord(digit)) == '#':
            num = int(number)

            if choice == 1:
                # Perform hexadecimal conversion
                result = format(num, 'x')
            elif choice == 0:
                # Perform binary conversion
                result = format(num, 'b')

            print(result)
        else:
            # Not yet received a '#' so
            number += digit
            print('{}'.format(number))

on_dtmf_digit('#')
on_dtmf_digit('1')
on_dtmf_digit('1')
on_dtmf_digit('5')
on_dtmf_digit('#')
