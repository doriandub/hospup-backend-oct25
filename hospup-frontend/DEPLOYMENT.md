# Hospup Frontend - Informations de Déploiement

## Domaines Vercel

### 🟢 Domaine Principal (Actif)
- **URL**: https://hospup-frontend-2-kappa.vercel.app
- **Status**: ✅ Actif et fonctionnel
- **Usage**: Production principale

### 🔴 Domaine Secondaire (Inactif)
- **URL**: https://hospup-frontend-nine.vercel.app  
- **Status**: ❌ 404 - Déploiement non trouvé
- **Action**: À supprimer/ignorer

## Backend Railway
- **URL**: https://web-production-b52f.up.railway.app
- **Status**: ✅ Actif et fonctionnel
- **Version**: 0.1.6

## Configuration
L'application frontend utilise l'environnement suivant :
- **API_BASE_URL**: `https://web-production-b52f.up.railway.app` (Railway backend)
- **Frontend**: `https://hospup-frontend-2-kappa.vercel.app` (Vercel)

## Notes
- Le domaine `hospup-frontend-nine.vercel.app` doit être ignoré (erreur 404)
- Utiliser uniquement `hospup-frontend-2-kappa.vercel.app` pour les tests et la production
- Authentification fonctionne correctement entre Vercel ↔ Railway
- Videos API utilise les paramètres supportés : `property_id` et `video_type`