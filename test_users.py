from auth.users import validate_user

usuario = validate_user(
    "christian@test.com",
    "123456"
)

print(usuario)