# Patch temporaire: skip ECS, send directly to Railway
# Dans mediaconvert-callback.py ligne 75-103, remplacer par:
            else:
                print(f"ℹ️ TEMP: Skipping ECS - sending directly to Railway (text overlays will be missing)")
