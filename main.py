from flask import Flask, request, jsonify
import dropbox
import requests
import random
import string
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ড্রপবক্স কনফিগারেশন
DROPBOX_TOKEN = "sl.u.AFnuT90fhojY3-z23_QDCeFwuGTHRkx0BLYni2BWorjZuADwyLj49B1DU042sEiQey3s-IkGWO_3rPPgMXc0wIEyQJPeAL4HowTNyqHK4TRiyEDDmOYsJ4hBIRG-h3X67-MvXrjvjodN8IRq-_QwHZRIFwiaS4IREoJjaTTobJh0woHXIyC-P_IqZ9vxWPmSBMVaWCJl5D-Jo_HpIRDO5h_XCFW7tbhgyjbNABIzzIcAFatBugXopghfOwv2N9jtzhOcSW_hFt9grN2eNWVGdOs3J0HmVplWmV8nGhgaiZ-NIT7As0vvy1mvlK5x6PSK2Uo4QJr1n8ZS_05SzsCXenp8NyKEc8HyhoBrG4pp-b2D-aRREdjo76JWz_ECIXw5cgOYy8cd5UsBwxmF3PDqJQVm8uGcuf_tS-MeEJLaRv8_Ni8KIKRqnhINobHzwMd3LRmJkFQbp6mI1UL_aNdBpYBQGbGcHfcaANWTL187109pA8ImOcGzfL36qlOobEYo0uplPMr18JP6WJOeTSfTYJBzm9pxnSw9EtfmRvVCvyJFbCYbWBJrQ2OoIHNU83iOKDA1-mn78zGLifMezmD-QmFDR_-RMFQ7kjq6EjNAlGqD-7I9knIuhzq2A1jm1OYgES75P9wVysNNtPf1GGmmt3OGisV7by7gELf4lD6F5zQPEAM0HrzMaScfYHo79jcZTYEnHGUI3NbTYP7obLiy-ndnM6ryKVvy-RYrmJOZHeTi5wgDVgavxEm0ViIbj_QN9Eety8fvGDOmbTHQjs4MEVqDtPV-Mu-CLRV-hSQBQC5JNEPYso0Pm5sIz0o6QezDfjWaYbBzBQjNXO1WKFyR9amTxNikX6gJ3b9vyuK6ror8qH1QR5lf_8W5MrsNcZOlR8m-g57LJxR61Rwk0J8OzJgnwBdYVdcWVS0o-rVNAgGWO17Krk0tc0KlyoGrhlbW2SFSvJGHe1QLVKN-hq43R0iwyPuPnd7Qu_R0YTEGUmVENhuJ2t9LeiGhFaOrNvUJji6tXZEjDeY-fpjEn0lPoAKlX1js0C5DPEc9RaAFJovP1ZlZaE6Tu1T2Wzn7NbrUG0WQ9oCEjH6V2T-9B04k5XVQsp10OMprJ8k61769yOIBAOlKoxEKhQmilBWGk8bcZmoU53RwcFU5_pTO2zeipwX0VoyFrzmQRy77-FbXXn2TrVV3rL3uwF9bijyHI0FqF__sg3Lu5S4MVy75cw4fJXevFCHNxFDhc2IQTVaZF3PDjinQ3I7oXRvlOA9e9mfI3-Zwx-w-hKxnhKFeKgAjkhE8Z-NmvFjQcBVQhc2MXVMmnM9lPKKjypKaIp4xkfoYALdZHRzLFkPIkhMFPMgLMjXDivrUzkdUXWPxp2ojxKbm6IWSyCnQut-UQU54MGQsYk1maDF-uaqzfNEdy_WRPvqHMKsfIKHQOr8Vr7fkWL1p9b_iUowHZmC0WJNJjBzfhMI"
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
