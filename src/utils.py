import random
import string

CHARACTERS = string.ascii_letters + string.digits


def generate_random_string(length: int = 16):
    return "".join(random.choice(CHARACTERS) for _ in range(length))
