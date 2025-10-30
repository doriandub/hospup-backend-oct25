#!/usr/bin/env python3
"""
Script pour importer le CSV nettoyé dans Supabase templates table
"""
import csv

csv_file = "/Users/doriandubord/Downloads/Videos copy-Grid view.csv"
output_file = "import_templates_clean.sql"

# Ouvrir le fichier SQL de sortie
with open(output_file, 'w', encoding='utf-8') as sql_file:
    sql_file.write("-- Import des templates depuis CSV Airtable (version nettoyée)\n")
    sql_file.write("-- Généré automatiquement\n\n")
    sql_file.write("BEGIN;\n\n")
    
    # Lire le CSV
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        
        for row in reader:
            count += 1
            
            # Nettoyer et préparer les données
            hotel_name = row.get('Hotel name', '').replace("'", "''")
            username = row.get('Username', '').replace("'", "''")
            property_type = row.get('Property', '').replace("'", "''")
            country = row.get('Country', '').replace("'", "''")
            video_link = row.get('Video link', '').replace("'", "''")
            account_link = row.get('Account link', '').replace("'", "''")
            audio = row.get('Audio', '').replace("'", "''")
            
            # Convertir les nombres
            try:
                followers = int(row.get('Followers', '0').replace(',', '').replace(' ', ''))
            except:
                followers = 0
                
            try:
                views = int(row.get('Views', '0').replace(',', '').replace(' ', ''))
            except:
                views = 0
                
            try:
                ratio = float(row.get('Ratio', '0').replace(',', '.'))
            except:
                ratio = 0.0
                
            try:
                likes = int(row.get('Likes', '0').replace(',', '').replace(' ', ''))
            except:
                likes = 0
                
            try:
                comments = int(row.get('Comments', '0').replace(',', '').replace(' ', ''))
            except:
                comments = 0
                
            try:
                duration = float(row.get('Duration', '0').replace(',', '.'))
            except:
                duration = 0.0
                
            # Script (JSON des clips) - échapper les apostrophes
            script = row.get('Script', '').replace("'", "''")
            
            # Slots (nombre de clips)
            try:
                slots = int(row.get('Slots', '0'))
            except:
                slots = 0
            
            # Générer l'INSERT avec ON CONFLICT pour éviter les doublons
            sql_file.write(f"""INSERT INTO public.templates (
  hotel_name, username, property_type, country, video_link, account_link, audio,
  followers, views, ratio, likes, comments, duration, script, slots
) VALUES (
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
);

""")
        
        sql_file.write(f"\nCOMMIT;\n\n")
        sql_file.write(f"-- Total: {count} templates importés\n")

print(f"✅ Fichier SQL généré: {output_file}")
print(f"📊 Total de templates: {count}")
print(f"\n📝 Prochaine étape:")
print(f"   1. Ouvre Supabase SQL Editor")
print(f"   2. Copie le contenu de: {output_file}")
print(f"   3. Colle et exécute dans Supabase")
