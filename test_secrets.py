from config.secrets_loader import SecretsLoader  # adjust path if needed

loader = SecretsLoader()

print("Mode:", loader.mode)
print("Loaded secrets:", loader.secrets)