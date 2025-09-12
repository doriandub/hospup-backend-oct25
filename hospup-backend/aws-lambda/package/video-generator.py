"""
AWS Lambda function pour générer des vidéos via FFmpeg direct
Solution rapide inspirée du système local qui fonctionnait
"""

import json
import boto3
import uuid
import os
import tempfile
import requests
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime

# MoviePy pour traitement vidéo (alternative à FFmpeg)
try:
    from moviepy.editor import VideoFileClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("⚠️ MoviePy not available, falling back to FFmpeg subprocess")

# Configuration AWS
S3_BUCKET = os.environ.get('S3_BUCKET', 'hospup-files')
S3_OUTPUT_PREFIX = os.environ.get('S3_OUTPUT_PREFIX', 'generated-videos/')

# Clients AWS
s3 = boto3.client('s3', region_name='eu-west-1')

def lambda_handler(event, context):
    """
    Point d'entrée principal pour la génération vidéo FFmpeg
    """
    temp_dir = None
    
    try:
        print(f"🚀 Starting FFmpeg video generation: {json.dumps(event, indent=2)}")
        
        # Parser les données de la timeline
        body = json.loads(event.get('body', '{}'))
        
        property_id = body.get('property_id')
        video_id = body.get('video_id')
        job_id = body.get('job_id', str(uuid.uuid4()))
        template_id = body.get('template_id')
        segments = body.get('segments', [])
        text_overlays = body.get('text_overlays', [])
        total_duration = body.get('total_duration', 30)
        webhook_url = body.get('webhook_url')
        
        # Valider les données
        if not property_id or not segments:
            return create_error_response(400, "Missing required data")
        
        print(f"📊 Processing {len(segments)} segments and {len(text_overlays)} texts")
        
        # Créer répertoire temporaire
        temp_dir = tempfile.mkdtemp(prefix=f'lambda_video_{job_id}_')
        print(f"📁 Created temp directory: {temp_dir}")
        
        # Étape 1: Télécharger et traiter chaque segment
        processed_segments = []
        for i, segment in enumerate(segments):
            segment_info = process_video_segment(
                segment=segment,
                segment_index=i,
                temp_dir=temp_dir
            )
            
            if segment_info:
                processed_segments.append(segment_info)
                print(f"✅ Processed segment {i+1}/{len(segments)}")
            else:
                print(f"⚠️ Failed to process segment {i+1}")
        
        if not processed_segments:
            raise Exception("No segments could be processed")
        
        print(f"🎞️ Successfully processed {len(processed_segments)} segments")
        
        # Étape 2: Assembler la vidéo finale
        final_video_path = assemble_final_video(
            segments=processed_segments,
            text_overlays=text_overlays,
            temp_dir=temp_dir,
            video_id=video_id
        )
        
        # Étape 3: Upload vers S3
        output_key = f"{S3_OUTPUT_PREFIX}{property_id}/{video_id}.mp4"
        thumbnail_key = f"thumbnails/{property_id}/{video_id}_thumb.jpg"
        
        # Upload vidéo finale
        with open(final_video_path, 'rb') as f:
            s3.upload_fileobj(
                f, S3_BUCKET, output_key,
                ExtraArgs={'ContentType': 'video/mp4'}
            )
        
        print(f"✅ Uploaded final video to S3: {output_key}")
        
        # Générer miniature
        thumbnail_path = generate_thumbnail(final_video_path, temp_dir, video_id)
        if thumbnail_path:
            with open(thumbnail_path, 'rb') as f:
                s3.upload_fileobj(
                    f, S3_BUCKET, thumbnail_key,
                    ExtraArgs={'ContentType': 'image/jpeg'}
                )
            print(f"✅ Uploaded thumbnail to S3: {thumbnail_key}")
        
        # Construire les URLs finales
        file_url = f"https://{S3_BUCKET}.s3.eu-west-1.amazonaws.com/{output_key}"
        thumbnail_url = f"https://{S3_BUCKET}.s3.eu-west-1.amazonaws.com/{thumbnail_key}" if thumbnail_path else None
        
        # Étape 4: Appeler le webhook de completion
        # 🔧 FIXUP: Utiliser le nouvel endpoint FFmpeg callback
        if webhook_url:
            # 🔧 HOTFIX: Utiliser l'endpoint alternatif pour contourner Railway cache
            webhook_url = webhook_url.replace("/aws-callback", "/aws-ffmpeg-webhook")
            webhook_data = {
                'video_id': video_id,
                'job_id': job_id,
                'status': 'COMPLETE',
                'file_url': file_url,
                'thumbnail_url': thumbnail_url,
                'duration': total_duration,
                'processing_time': datetime.utcnow().isoformat()
            }
            
            try:
                response = requests.post(
                    webhook_url,
                    json=webhook_data,
                    timeout=30
                )
                print(f"✅ Webhook called successfully: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Webhook failed but video generated: {e}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'video_id': video_id,
                'job_id': job_id,
                'file_url': file_url,
                'thumbnail_url': thumbnail_url,
                'segments_processed': len(processed_segments)
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Lambda processing error: {error_msg}")
        
        # Appeler le webhook avec l'erreur
        if 'webhook_url' in locals() and webhook_url:
            try:
                # 🔧 HOTFIX: Utiliser l'endpoint alternatif pour contourner Railway cache
                webhook_url = webhook_url.replace("/aws-callback", "/aws-ffmpeg-webhook")
                requests.post(
                    webhook_url,
                    json={
                        'video_id': video_id if 'video_id' in locals() else 'unknown',
                        'job_id': job_id if 'job_id' in locals() else 'unknown',
                        'status': 'ERROR',
                        'error': error_msg
                    },
                    timeout=10
                )
            except:
                pass
        
        return create_error_response(500, error_msg)
    
    finally:
        # Nettoyer le répertoire temporaire
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print("🧹 Cleaned up temporary files")
            except Exception as e:
                print(f"⚠️ Cleanup failed: {e}")


def process_video_segment(
    segment: Dict[str, Any], 
    segment_index: int, 
    temp_dir: str
) -> Optional[Dict[str, Any]]:
    """Traiter un segment vidéo individuel avec FFmpeg"""
    try:
        video_url = segment.get('video_url', '')
        duration = segment.get('duration', 3.0)
        order = segment.get('order', segment_index)
        
        if not video_url:
            print(f"⚠️ No video URL for segment {segment_index}")
            return None
        
        print(f"🎬 Processing segment {segment_index}: {duration}s from {video_url}")
        
        # Télécharger la vidéo source
        source_path = os.path.join(temp_dir, f"source_{segment_index}.mp4")
        
        response = requests.get(video_url, stream=True, timeout=60)
        if response.status_code != 200:
            print(f"❌ Failed to download video {segment_index}: HTTP {response.status_code}")
            return None
        
        with open(source_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"📥 Downloaded source video: {os.path.getsize(source_path):,} bytes")
        
        # Extraire le segment avec la durée exacte
        segment_path = os.path.join(temp_dir, f"segment_{segment_index}.mp4")
        
        # Chercher FFmpeg dans différents emplacements (layer FFmpeg est dans /opt/bin/)
        ffmpeg_paths = ['/opt/bin/ffmpeg', '/opt/ffmpeg', '/usr/bin/ffmpeg', 'ffmpeg']
        ffmpeg_cmd = None
        
        for path in ffmpeg_paths:
            if os.path.exists(path) or path == 'ffmpeg':  # 'ffmpeg' sera testé via subprocess
                ffmpeg_cmd = path
                break
        
        if not ffmpeg_cmd:
            print(f"❌ FFmpeg not found in any of: {ffmpeg_paths}")
            # Fallback: copier le fichier sans traitement pour le test
            import shutil
            shutil.copy2(source_path, segment_path)
            os.remove(source_path)
            return {"path": segment_path, "duration": duration, "order": order}
        
        cmd = [
            ffmpeg_cmd, "-y", "-i", source_path,
            "-ss", "0", "-t", str(duration),
            "-c:v", "libx264", "-c:a", "aac",
            "-r", "30", "-crf", "23",
            "-avoid_negative_ts", "make_zero",
            segment_path
        ]
        
        print(f"🔧 Using FFmpeg: {ffmpeg_cmd}")
        print(f"🎬 Command: {' '.join(cmd)}")
        
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and os.path.exists(segment_path):
                os.remove(source_path)
                print(f"✅ FFmpeg segment created: {os.path.getsize(segment_path):,} bytes")
                return {"path": segment_path, "duration": duration, "order": order}
            else:
                print(f"❌ FFmpeg failed: {result.stderr}")
                # Fallback: copier le fichier sans traitement
                import shutil
                shutil.copy2(source_path, segment_path)
                os.remove(source_path)
                return {"path": segment_path, "duration": duration, "order": order}
                
        except Exception as e:
            print(f"❌ FFmpeg error: {e}")
            # Fallback: copier le fichier sans traitement
            import shutil
            shutil.copy2(source_path, segment_path)
            os.remove(source_path)
            return {"path": segment_path, "duration": duration, "order": order}
            
    except Exception as e:
        print(f"❌ Error processing segment {segment_index}: {e}")
        return None


def assemble_final_video(
    segments: List[Dict[str, Any]], 
    text_overlays: List[Dict[str, Any]], 
    temp_dir: str, 
    video_id: str
) -> str:
    """Assembler la vidéo finale avec concaténation FFmpeg"""
    
    # Trier par ordre
    segments.sort(key=lambda x: x.get("order", 0))
    
    final_video_path = os.path.join(temp_dir, f"final_{video_id}.mp4")
    
    # Chercher FFmpeg pour l'assemblage (layer FFmpeg est dans /opt/bin/)
    ffmpeg_paths = ['/opt/bin/ffmpeg', '/opt/ffmpeg', '/usr/bin/ffmpeg', 'ffmpeg']
    ffmpeg_cmd = None
    
    for path in ffmpeg_paths:
        if os.path.exists(path) or path == 'ffmpeg':
            ffmpeg_cmd = path
            break
    
    if not ffmpeg_cmd:
        print("❌ FFmpeg not available, using first segment as final video")
        import shutil
        shutil.copy2(segments[0]["path"], final_video_path)
        print(f"📹 Fallback video ready: {os.path.getsize(final_video_path):,} bytes")
        return final_video_path
    
    print(f"🔧 Using FFmpeg for assembly: {ffmpeg_cmd}")
    
    if len(segments) == 1:
        # Un seul segment - mise à l'échelle 9:16
        cmd = [
            ffmpeg_cmd, "-y", "-i", segments[0]["path"],
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-c:a", "aac",
            "-r", "30", "-crf", "23",
            final_video_path
        ]
        
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"⚠️ FFmpeg scaling failed, using original: {result.stderr}")
            import shutil
            shutil.copy2(segments[0]["path"], final_video_path)
        
        print("📹 Single segment processed")
    else:
        # Multiples segments - concaténation
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                path = segment['path'].replace("'", "\\'")
                f.write(f"file '{path}'\n")
        
        # Concaténer avec mise à l'échelle 9:16
        cmd = [
            ffmpeg_cmd, "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-c:a", "aac",
            "-r", "30", "-crf", "23",
            final_video_path
        ]
        
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"⚠️ FFmpeg concatenation failed, using first segment: {result.stderr}")
            import shutil
            shutil.copy2(segments[0]["path"], final_video_path)
        else:
            print(f"📹 Concatenated {len(segments)} segments successfully")
    
    # TODO: Ajouter text overlays si nécessaire
    if text_overlays:
        print(f"📝 Skipping {len(text_overlays)} text overlays (not implemented yet)")
    
    if not os.path.exists(final_video_path):
        raise Exception("Final video file was not created")
    
    return final_video_path


def generate_thumbnail(video_path: str, temp_dir: str, video_id: str) -> Optional[str]:
    """Générer une miniature de la vidéo"""
    try:
        import subprocess
        thumbnail_path = os.path.join(temp_dir, f"{video_id}_thumb.jpg")
        
        ffmpeg_cmd = [
            "/opt/bin/ffmpeg", "-y", "-i", video_path,
            "-ss", "2", "-vframes", "1",
            "-vf", "scale=640:1138:force_original_aspect_ratio=decrease,pad=640:1138:(ow-iw)/2:(oh-ih)/2:black",
            "-q:v", "2",
            thumbnail_path
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            print("✅ Thumbnail generated successfully")
            return thumbnail_path
        else:
            print(f"⚠️ Thumbnail generation failed: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error generating thumbnail: {e}")
        return None


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Créer une réponse d'erreur"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }