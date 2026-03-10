"""
Genera hashes bcrypt para agregar/cambiar contraseñas en users.yaml.

Uso:
    python auth/generar_password.py
"""
import bcrypt

def generar_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

if __name__ == "__main__":
    print("=== Generador de contraseñas para users.yaml ===\n")
    while True:
        pwd = input("Ingresa la contraseña (o Enter para salir): ").strip()
        if not pwd:
            break
        print(f"Hash: {generar_hash(pwd)}\n")
