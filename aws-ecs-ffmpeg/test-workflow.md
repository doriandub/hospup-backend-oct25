# 🧪 Test du Workflow Optimisé

## Avant le build ECS (test partiel)

Tu peux déjà tester que MediaConvert fonctionne:

1. Va sur video-debug
2. Clique "Test Video Generation"
3. Vérifie les logs Lambda:
   ```bash
   aws logs tail /aws/lambda/hospup-video-generator --follow --region eu-west-1
   ```

Tu devrais voir:
- ✅ "Storing text overlays for ECS FFmpeg post-processing"
- ✅ "MediaConvert job submitted"

## Après le build ECS (test complet)

Une fois ./deploy.sh terminé:

1. Même test sur video-debug
2. Vérifie les logs ECS:
   ```bash
   aws logs tail /ecs/hospup-ffmpeg-worker --follow --region eu-west-1
   ```

Tu devrais voir:
- ✅ "OPTIMIZED MODE: Adding text overlays to MediaConvert video"
- ✅ "FFmpeg completed successfully"
- ✅ "Job completed in X.Xs (mode=optimized)"

## Commandes utiles pendant le build

Voir progression du build:
```bash
tail -f build.log  # dans le terminal où tu lances deploy.sh
```

Voir les workers ECS:
```bash
aws ecs list-tasks --cluster hospup-video-processing --region eu-west-1
```

Voir la queue SQS:
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs \
  --attribute-names ApproximateNumberOfMessages \
  --region eu-west-1
```
