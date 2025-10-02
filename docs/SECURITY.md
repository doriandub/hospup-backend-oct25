# 🔒 Security Guidelines

## ⚠️ CRITICAL: Credential Rotation Required

**IMMEDIATE ACTION REQUIRED** if you have the old repository with hardcoded credentials:

### 1. Rotate Database Credentials
```bash
# 1. Go to Supabase Dashboard
# 2. Settings → Database → Reset database password
# 3. Update DB_PASSWORD in Railway environment variables
# 4. Redeploy backend
```

### 2. Rotate AWS IAM Credentials
```bash
# 1. Go to AWS IAM Console
# 2. Delete old access key: AKIAWAFBWF6JS265QXQC
# 3. Create new access key
# 4. Update S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY in Railway
# 5. Redeploy backend
```

### 3. Rotate JWT Secrets
```bash
# Generate new secrets
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_REFRESH_SECRET=' + secrets.token_urlsafe(32))"

# Update in Railway environment variables
# This will invalidate all existing user sessions
```

---

## 🛡️ Security Best Practices

### Environment Variables

#### ✅ DO:
- Store all secrets in environment variables
- Use `.env.example` as templates (no real values)
- Use different secrets for dev/staging/production
- Rotate secrets regularly (every 90 days)
- Use Railway/Vercel dashboards for production secrets

#### ❌ DON'T:
- Never commit `.env` or `.env.local` files
- Never hardcode credentials in source code
- Never share secrets in chat/email/Slack
- Never use the same secrets across environments
- Never put AWS credentials in frontend code

### Pre-commit Checklist

Before every commit:
```bash
# 1. Check for accidentally staged secrets
git diff --cached | grep -i "password\|secret\|key\|token"

# 2. Verify .env files are ignored
git status | grep -i ".env"

# 3. Review changed files
git diff --cached
```

### AWS S3 Security

#### Frontend S3 Access (SECURE METHOD):
```typescript
// ✅ CORRECT: Use presigned URLs from backend
const { upload_url } = await fetch('/api/upload/presigned-url', {
  method: 'POST',
  body: JSON.stringify({ file_name, content_type })
})

await fetch(upload_url, {
  method: 'PUT',
  body: file
})
```

```typescript
// ❌ WRONG: Never use AWS credentials in frontend
const s3 = new AWS.S3({
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,  // NEVER DO THIS!
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
})
```

#### S3 Bucket Configuration:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::hospup-files/*",
        "arn:aws:s3:::hospup-files"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
```

### Database Security

#### Connection Security:
- ✅ Always use SSL/TLS connections
- ✅ Use connection pooling (prevent exhaustion)
- ✅ Use prepared statements (prevent SQL injection)
- ✅ Enable row-level security (RLS) in Supabase

#### Query Safety:
```python
# ✅ CORRECT: Use SQLAlchemy ORM or parameterized queries
user = await db.execute(
    select(User).where(User.email == email)
)

# ❌ WRONG: Never use string interpolation
query = f"SELECT * FROM users WHERE email = '{email}'"  # SQL INJECTION RISK!
```

### Authentication Security

#### JWT Token Handling:
```typescript
// ✅ CORRECT: Store in httpOnly cookies
res.cookie('access_token', token, {
  httpOnly: true,
  secure: true,
  sameSite: 'none'
})

// ❌ WRONG: Never store in localStorage
localStorage.setItem('token', token)  // XSS vulnerability!
```

#### Password Security:
- ✅ Use bcrypt with min 10 rounds
- ✅ Enforce strong password requirements
- ✅ Implement rate limiting on auth endpoints
- ✅ Add MFA/2FA support

### API Security

#### Input Validation:
```python
# ✅ CORRECT: Use Pydantic schemas
class LoginRequest(BaseModel):
    email: EmailStr  # Validates email format
    password: str = Field(min_length=8, max_length=100)
```

#### Rate Limiting:
```python
# Implement per-endpoint rate limits
@router.post("/login")
@limiter.limit("5/minute")  # Max 5 attempts per minute
async def login(...):
    ...
```

---

## 🚨 Incident Response

### If Credentials Are Compromised:

1. **Immediate Actions** (within 1 hour):
   - Rotate compromised credentials
   - Review access logs for suspicious activity
   - Block suspicious IP addresses
   - Notify team

2. **Investigation** (within 24 hours):
   - Check database for unauthorized changes
   - Review S3 bucket access logs
   - Check Lambda execution logs
   - Identify scope of breach

3. **Recovery** (within 1 week):
   - Implement additional security measures
   - Update security documentation
   - Conduct security audit
   - Train team on security best practices

### Reporting Security Issues

**DO NOT** create public GitHub issues for security vulnerabilities.

Instead:
1. Email: security@hospup.com (or project owner)
2. Use encrypted communication
3. Provide detailed steps to reproduce
4. Wait for acknowledgment before public disclosure

---

## 🔍 Security Checklist

### Development Environment
- [ ] `.env` files in `.gitignore`
- [ ] `.env.example` templates created
- [ ] No hardcoded secrets in code
- [ ] Pre-commit hooks configured

### Production Environment
- [ ] All secrets rotated from development
- [ ] HTTPS enforced (no HTTP)
- [ ] CORS configured correctly
- [ ] Rate limiting enabled
- [ ] Error tracking configured (Sentry)
- [ ] Database backups automated
- [ ] S3 bucket private (no public access)
- [ ] CloudFront CDN configured
- [ ] JWT tokens in httpOnly cookies
- [ ] Password strength requirements
- [ ] Input validation on all endpoints

### Monitoring
- [ ] CloudWatch alarms configured
- [ ] Suspicious login alerts
- [ ] Failed authentication monitoring
- [ ] S3 access logging enabled
- [ ] Lambda error alerts
- [ ] Database connection monitoring

---

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Next.js Security](https://nextjs.org/docs/advanced-features/security-headers)

---

**Last Updated:** 2025-10-02
**Review Frequency:** Quarterly
