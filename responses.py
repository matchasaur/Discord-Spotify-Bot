from random import choice, randint

def get_response(user_input: str) -> str:
    lowered: str = user_input.lower()
    
    if lowered == '':
        return 'You are quiet'
    elif 'hello' in lowered:
        return 'Greetings!'    