from flask import Flask, request, jsonify
import dropbox
import requests
import random
import string
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ড্রপবক্স কনফিগারেশন
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")
dbx = dropbox.Dropbox(DROPBOX_TOKEN)

# ইউআইডি স্টোরেজ
generated_uuids = set()

CHUNK_SIZE = 8 * 1024 * 1024  # 8MB চাঙ্ক সাইজ

def generate_custom_uuid():
    """ কাস্টম UUID জেনারেট করে """
    characters = string.ascii_uppercase + string.digits
    while True:
        parts = [''.join(random.choices(characters, k=4)) for _ in range(4)]
        custom_uuid = '-'.join(parts)
        if custom_uuid not in generated_uuids:
            generated_uuids.add(custom_uuid)
            return custom_uuid

def upload_from_url(url, dbx_path, dbx_instance):
    """ যেকোনো ফাইল URL থেকে ড্রপবক্সে চাঙ্ক করে আপলোড করা হয় (সঠিক অফসেট গণনা সহ) """
    try:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            
            chunk_generator = response.iter_content(chunk_size=CHUNK_SIZE)
            first_chunk = next(chunk_generator)

            # প্রথম চাঙ্ক আপলোড এবং সেশন শুরু
            session_start = dbx_instance.files_upload_session_start(first_chunk)
            cursor = dropbox.files.UploadSessionCursor(session_id=session_start.session_id, offset=len(first_chunk))
            commit = dropbox.files.CommitInfo(path=dbx_path, mode=dropbox.files.WriteMode.overwrite)

            # পরবর্তী চাঙ্কগুলো একটার পর একটা আপলোড হবে (সঠিক অফসেট মেইনটেইন করে)
            for chunk in chunk_generator:
                if chunk:
                    dbx_instance.files_upload_session_append_v2(chunk, cursor)
                    cursor.offset += len(chunk)  # ✅ সঠিকভাবে অফসেট আপডেট করা হচ্ছে

            # ফাইল আপলোড শেষ
            dbx_instance.files_upload_session_finish(b'', cursor, commit)
    except Exception as e:
        raise Exception(f"Error uploading from URL: {e}")

@app.route('/up', methods=['GET'])
def direct_upload():
    """ ইউজার থেকে GET রিকোয়েস্ট নিয়ে লিংক প্রসেস করে ড্রপবক্সে আপলোড করে """
    combined_links = request.query_string.decode()

    if not combined_links:
        return jsonify({"error": "No URL provided"}), 400

    # @ দ্বারা বিভক্ত করা
    links = combined_links.split('@')

    # `hd=` এবং `sd=` লিংক আলাদা করা
    hd_link = next((link.split('hd=')[1] for link in links if 'hd=' in link), None)
    sd_link = next((link.split('sd=')[1] for link in links if 'sd=' in link), None)

    if not hd_link and not sd_link:
        return jsonify({"error": "No valid HD or SD link provided"}), 400

    try:
        links = {}

        if hd_link:
            custom_uuid = generate_custom_uuid()
            dbx_path = f"/{custom_uuid}_HD.mp4"
            upload_from_url(hd_link, dbx_path, dbx)
            shared_link = dbx.sharing_create_shared_link_with_settings(dbx_path)
            links['hd'] = shared_link.url.replace("dl=0", "raw=1")

        if sd_link:
            custom_uuid = generate_custom_uuid()
            dbx_path = f"/{custom_uuid}_SD.mp4"
            upload_from_url(sd_link, dbx_path, dbx)
            shared_link = dbx.sharing_create_shared_link_with_settings(dbx_path)
            links['sd'] = shared_link.url.replace("dl=0", "raw=1")

        return jsonify({"success": True, "links": links})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
