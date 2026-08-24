import bcrypt

# Le mot de passe que vous souhaitez utiliser
mot_de_passe_clair = "123456789"

# Génération du hash sécurisé
hash_securise = bcrypt.hashpw(mot_de_passe_clair.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print("\n--- COPIEZ LA LIGNE CI-DESSOUS ---")
print(hash_securise)
print("----------------------------------\n")