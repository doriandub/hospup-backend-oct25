# Dockerfile pour ECS Fargate FFmpeg Worker (zéro cold start)
FROM public.ecr.aws/docker/library/python:3.11-slim

# Install FFmpeg + fontconfig
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fontconfig \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Télécharger polices Google Fonts (complètes, non-subset)
# 4 familles de polices avec 4 variantes chacune (Regular, Bold, Italic, BoldItalic)
# Total: 16 font variants - gratuites, libres de droits commerciaux (OFL license)
RUN mkdir -p /usr/share/fonts/truetype/google-fonts

# 1-4. Roboto (Sans-Serif moderne, ultra-polyvalente)
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Roboto-Regular.ttf \
    https://github.com/google/roboto/raw/main/src/hinted/Roboto-Regular.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Roboto-Bold.ttf \
    https://github.com/google/roboto/raw/main/src/hinted/Roboto-Bold.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Roboto-Italic.ttf \
    https://github.com/google/roboto/raw/main/src/hinted/Roboto-Italic.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Roboto-BoldItalic.ttf \
    https://github.com/google/roboto/raw/main/src/hinted/Roboto-BoldItalic.ttf

# 5-8. Open Sans (Sans-Serif, très lisible)
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/OpenSans-Regular.ttf \
    https://github.com/googlefonts/opensans/raw/main/fonts/ttf/OpenSans-Regular.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/OpenSans-Bold.ttf \
    https://github.com/googlefonts/opensans/raw/main/fonts/ttf/OpenSans-Bold.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/OpenSans-Italic.ttf \
    https://github.com/googlefonts/opensans/raw/main/fonts/ttf/OpenSans-Italic.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/OpenSans-BoldItalic.ttf \
    https://github.com/googlefonts/opensans/raw/main/fonts/ttf/OpenSans-BoldItalic.ttf

# 9-12. Montserrat (Sans-Serif géométrique, style moderne)
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Montserrat-Regular.ttf \
    https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Montserrat-Bold.ttf \
    https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Montserrat-Italic.ttf \
    https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Italic.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Montserrat-BoldItalic.ttf \
    https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-BoldItalic.ttf

# 13-16. Lato (Sans-Serif élégante)
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Lato-Regular.ttf \
    https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Lato-Bold.ttf \
    https://github.com/google/fonts/raw/main/ofl/lato/Lato-Bold.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Lato-Italic.ttf \
    https://github.com/google/fonts/raw/main/ofl/lato/Lato-Italic.ttf
RUN wget -q -O /usr/share/fonts/truetype/google-fonts/Lato-BoldItalic.ttf \
    https://github.com/google/fonts/raw/main/ofl/lato/Lato-BoldItalic.ttf

# Note: Additional fonts (Merriweather, Playfair Display, Bebas Neue, Oswald) can be added
# Current 16 variants cover most use cases with Regular, Bold, Italic, BoldItalic support

# Rebuild font cache
RUN fc-cache -fv

# Install Python dependencies
RUN pip install --no-cache-dir boto3 requests

# Copy worker script
WORKDIR /app
COPY worker.py /app/

# Environment variables
ENV AWS_DEFAULT_REGION=eu-west-1
ENV SQS_QUEUE_URL=""
ENV WEBHOOK_URL=""

# Run worker (consumes SQS messages forever)
CMD ["python", "-u", "worker.py"]
