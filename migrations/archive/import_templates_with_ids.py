#!/usr/bin/env python3
"""
Script pour importer le CSV Supabase (avec IDs) dans la table templates
"""
import csv

csv_file = "/Users/doriandubord/Downloads/templates_rows.csv"
output_file = "import_with_ids.sql"

with open(output_file, 'w', encoding='utf-8') as sql_file:
    sql_file.write("-- Import des templates depuis CSV Supabase (avec IDs)\n\n")
    sql_file.write("BEGIN;\n\n")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        
        for row in reader:
            count += 1
            
            # Récupérer toutes les colonnes (déjà au bon format)
            id_val = row.get('id', '')
            created_at = row.get('created_at', '')
            updated_at = row.get('updated_at', '')
            hotel_name = row.get('hotel_name', '').replace("'", "''")
            username = row.get('username', '').replace("'", "''")
            property_type = row.get('property_type', '').replace("'", "''")
            country = row.get('country', '').replace("'", "''")
            video_link = row.get('video_link', '').replace("'", "''")
            account_link = row.get('account_link', '').replace("'", "''")
            audio = row.get('audio', '').replace("'", "''")
            
            # Nombres
            try:
                followers = int(row.get('followers', '0'))
            except:
                followers = 0
                
            try:
                views = int(row.get('views', '0'))
            except:
                views = 0
                
            try:
                ratio = float(row.get('ratio', '0'))
            except:
                ratio = 0.0
                
            try:
                likes = int(row.get('likes', '0'))
            except:
                likes = 0
                
            try:
                comments = int(row.get('comments', '0'))
            except:
                comments = 0
                
            try:
                duration = float(row.get('duration', '0'))
            except:
                duration = 0.0
            
            # Script (JSON)
            script = row.get('script', '').replace("'", "''")
            
            try:
                slots = int(row.get('slots', '0'))
            except:
                slots = 0
            
            # INSERT avec l'ID fourni
            sql_file.write(f"""INSERT INTO public.templates (
  id, created_at, updated_at, hotel_name, username, property_type, country, 
  video_link, account_link, audio, followers, views, ratio, likes, comments, 
  duration, script, slots
) VALUES (
  '{id_val}',
  '{created_at}',
  '{updated_at}',
  '{hotel_name}',
  '{username}',
  '{property_type}',
  '{country}',
  '{video_link}',
  '{account_link}',
  '{audio}',
  {followers},
  {views},
  {ratio},
  {likes},
  {comments},
  {duration},
  '{script}',
  {slots}
) ON CONFLICT (id) DO UPDATE SET
  updated_at = EXCLUDED.updated_at,
  hotel_name = EXCLUDED.hotel_name,
  username = EXCLUDED.username,
  property_type = EXCLUDED.property_type,
  country = EXCLUDED.country,
  video_link = EXCLUDED.video_link,
  account_link = EXCLUDED.account_link,
  audio = EXCLUDED.audio,
  followers = EXCLUDED.followers,
  views = EXCLUDED.views,
  ratio = EXCLUDED.ratio,
  likes = EXCLUDED.likes,
  comments = EXCLUDED.comments,
  duration = EXCLUDED.duration,
  script = EXCLUDED.script,
  slots = EXCLUDED.slots;

""")
        
        sql_file.write(f"\nCOMMIT;\n\n")
        sql_file.write(f"-- Total: {count} templates importés/mis à jour\n")

print(f"✅ Fichier SQL généré: {output_file}")
print(f"📊 Total de templates: {count}")
print(f"\n🎯 Le script utilise ON CONFLICT pour éviter les doublons")
print(f"   et mettre à jour les lignes existantes")
