# 🧪 Guide de Test - AWS Lambda + MediaConvert

## 📋 Tests à effectuer après setup

### **1️⃣ Test Backend AWS Integration**

```bash
# Test direct de l'endpoint Railway
curl -X POST https://web-production-b52f.up.railway.app/api/v1/video-generation/generate-from-viral-template \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "test-property",
    "source_type": "viral_template_composer", 
    "source_data": {
      "template_id": "test-template",
      "slot_assignments": [
        {
          "slotId": "slot_1",
          "videoId": "video_1"
        }
      ],
      "text_overlays": [
        {
          "content": "Test Text",
          "start_time": 0,
          "end_time": 3,
          "position": {"x": 50, "y": 50, "anchor": "center"},
          "style": {"color": "#ffffff", "font_size": 24, "opacity": 1}
        }
      ],
      "total_duration": 30
    },
    "language": "fr"
  }'
```

### **2️⃣ Test Lambda Direct**

```bash
# Test de la fonction Lambda directement
aws lambda invoke \
  --function-name hospup-video-generator \
  --payload '{
    "body": "{
      \"property_id\": \"test\",
      \"segments\": [
        {
          \"id\": \"seg1\",
          \"video_url\": \"s3://hospup-videos/test.mp4\",
          \"start_time\": 0,
          \"end_time\": 10,
          \"duration\": 10,
          \"order\": 1
        }
      ],
      \"text_overlays\": [],
      \"total_duration\": 10
    }"
  }' \
  response.json

cat response.json
```

### **3️⃣ Test Frontend Timeline**

1. **Aller à** : `http://localhost:3000/dashboard/compose/[template-id]`
2. **Créer une timeline** avec :
   - Au moins 2 clips vidéo
   - 1-2 text overlays
   - Durée totale ~30 secondes
3. **Cliquer "Générer la vidéo"**
4. **Vérifier** :
   - ✅ Statut change à "processing"  
   - ✅ Video créée dans database avec `status='processing'`
   - ✅ Lambda invoquée sans erreur
   - ✅ Callback webhook reçu (si configuré)

### **4️⃣ Monitoring AWS**

```bash
# Vérifier les logs Lambda
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/hospup"

# Vérifier jobs MediaConvert
aws mediaconvert list-jobs --max-results 10 --region eu-west-1

# Vérifier contenu S3
aws s3 ls s3://hospup-videos/ --recursive
```

### **5️⃣ Test de Status Check**

```bash
# Test de la fonction de statut
aws lambda invoke \
  --function-name hospup-video-status \
  --payload '{
    "pathParameters": {
      "jobId": "test-job-id"
    }
  }' \
  status-response.json

cat status-response.json
```

## ✅ Checklist de Validation

- [ ] **Variables Railway** configurées et déployées
- [ ] **IAM Roles** créés (HospupMediaConvertRole, HospupLambdaExecutionRole)
- [ ] **S3 Bucket** créé avec CORS configuré
- [ ] **Lambda Functions** déployées (hospup-video-generator, hospup-video-status)
- [ ] **Test Backend** : endpoint répond 200
- [ ] **Test Lambda** : invocation réussie
- [ ] **Test Frontend** : timeline → génération fonctionne
- [ ] **Test Database** : video créée avec status='processing'
- [ ] **Test S3** : fichiers uploadés dans le bucket

## 🚨 Debugging

### Erreurs communes :

1. **403 Forbidden** → Vérifier les permissions IAM
2. **500 Internal Error** → Vérifier les logs Lambda
3. **Infinite loading** → Vérifier webhook callback
4. **Missing S3 bucket** → Vérifier nom du bucket dans variables

### Logs utiles :

```bash
# Logs Railway
# Voir dans Railway Dashboard > Deployments > Logs

# Logs Lambda
aws logs tail /aws/lambda/hospup-video-generator --follow

# Logs MediaConvert
aws logs tail /aws/mediaconvert --follow
```

## 🎯 Métriques de Succès

- ✅ **Latence** : Timeline → Lambda < 5 secondes
- ✅ **Throughput** : Génération MediaConvert < 2 minutes
- ✅ **Fiabilité** : 95%+ de taux de succès
- ✅ **Coût** : < 0.02€ par vidéo générée