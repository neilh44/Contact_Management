from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from main import VisitingCardProcessor
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
CORS(app)

# Initialize processor
processor = VisitingCardProcessor()

# Configuration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Serve the main HTML page"""
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'index.html not found'}), 404

@app.route('/api/process-visiting-card', methods=['POST'])
def process_visiting_card():
    """Process uploaded visiting card image"""
    print("🔄 Received request to process visiting card")
    print(f"📁 Files in request: {list(request.files.keys())}")
    print(f"📋 Form data: {dict(request.form)}")
    
    try:
        # Check if file is in request
        if 'image' not in request.files:
            print("❌ No image file in request")
            return jsonify({'success': False, 'error': 'No image file provided'}), 400
        
        file = request.files['image']
        
        # Read file content to check actual size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        print(f"📄 File received: {file.filename}")
        print(f"📏 Actual file size: {file_size} bytes")
        
        # Check if file is selected and has content
        if file.filename == '' or file_size == 0:
            print("❌ Empty file or no file selected")
            return jsonify({'success': False, 'error': 'No file selected or file is empty'}), 400
        
        # Check file extension
        if not allowed_file(file.filename):
            print(f"❌ Unsupported file format: {file.filename}")
            return jsonify({'success': False, 'error': 'Unsupported file format'}), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        print(f"💾 Saving file to: {temp_path}")
        
        file.save(temp_path)
        
        # Verify file was saved correctly
        if os.path.exists(temp_path):
            saved_size = os.path.getsize(temp_path)
            print(f"✅ File saved successfully. Size on disk: {saved_size} bytes")
        else:
            print("❌ File was not saved properly")
            return jsonify({'success': False, 'error': 'Failed to save uploaded file'}), 500
        
        try:
            print("🤖 Starting GPT Vision processing...")
            # Process the image
            result = processor.process_visiting_card(temp_path)
            print(f"✅ Processing result: {result.get('success', False)}")
            
            if result.get('success'):
                print(f"📊 Tokens used: {result.get('tokens_used', 0)}")
                print(f"👤 Contact ID: {result.get('contact_id', 'N/A')}")
                print(f"📇 Contact info keys: {list(result.get('contact_info', {}).keys())}")
            else:
                print(f"❌ Processing error: {result.get('error', 'Unknown error')}")
                # Print raw response for debugging
                if 'raw_response' in result:
                    print(f"🔍 Raw GPT response: {result['raw_response'][:500]}...")
            
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print("🗑️ Temporary file cleaned up")
            
            return jsonify(result)
            
        except Exception as e:
            print(f"💥 Exception during processing: {str(e)}")
            # Clean up on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print("🗑️ Temporary file cleaned up after error")
            return jsonify({'success': False, 'error': f'Processing failed: {str(e)}'}), 500
            
    except Exception as e:
        print(f"💥 General exception: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/query-contacts', methods=['POST'])
def query_contacts():
    """Query stored contacts"""
    print("🔍 Received request to query contacts")
    try:
        data = request.get_json()
        print(f"📋 Query data: {data}")
        query = data.get('query', '')
        limit = data.get('limit', 5)
        
        if not query:
            print("❌ Empty query")
            return jsonify({'success': False, 'error': 'Query is required'}), 400
        
        print(f"🔎 Searching for: '{query}' (limit: {limit})")
        result = processor.query_contacts(query, limit)
        print(f"✅ Query result: Found {len(result.get('results', []))} contacts")
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Query exception: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/all-contacts', methods=['GET'])
def get_all_contacts():
    """Get all stored contacts"""
    print("📇 Received request to get all contacts")
    try:
        result = processor.get_all_contacts()
        print(f"✅ Retrieved {len(result.get('contacts', []))} total contacts")
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Get all contacts exception: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        stats = processor.get_system_stats()
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug-contacts', methods=['GET'])
def debug_contacts():
    """Debug endpoint to see all stored contacts"""
    try:
        print("🔍 Debug: Getting all contacts for inspection")
        all_contacts = processor.get_all_contacts()
        
        debug_info = {
            'total_contacts': len(all_contacts.get('contacts', [])),
            'contacts': []
        }
        
        for contact in all_contacts.get('contacts', []):
            debug_contact = {
                'id': contact.get('id'),
                'metadata': contact.get('metadata', {}),
                'contact_data_keys': list(contact.get('contact_data', {}).keys()) if contact.get('contact_data') else [],
                'sample_data': {
                    'company': contact.get('contact_data', {}).get('company'),
                    'business_type': contact.get('metadata', {}).get('business_type')
                }
            }
            debug_info['contacts'].append(debug_contact)
            print(f"📋 Contact: {debug_contact['sample_data']['company']} - {debug_contact['sample_data']['business_type']}")
        
        return jsonify({'success': True, 'debug_info': debug_info})
        
    except Exception as e:
        print(f"💥 Debug error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'visiting-card-extractor',
        'version': '1.0.0'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting Visiting Card Extractor API...")
    print("Available endpoints:")
    print("  GET  /                          - Web interface")
    print("  POST /api/process-visiting-card - Process image")
    print("  POST /api/query-contacts        - Search contacts")
    print("  GET  /api/all-contacts          - Get all contacts")
    print("  GET  /api/stats                 - System statistics")
    print("  GET  /api/health                - Health check")
    
    app.run(debug=True, host='0.0.0.0', port=5000)