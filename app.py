from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from auth_manager import AuthManager, require_auth
from supabase_config import SupabaseManager, SupabaseVectorStore
from main import VisitingCardProcessor
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Initialize managers
auth_manager = AuthManager()
supabase_manager = SupabaseManager()
processor = VisitingCardProcessor()
supabase_vector_store = SupabaseVectorStore(supabase_manager)

# Configuration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============ PUBLIC ROUTES ============

@app.route('/')
def index():
    """Serve the main HTML page"""
    try:
        with open('secure_index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        try:
            with open('index.html', 'r') as f:
                return f.read()
        except FileNotFoundError:
            return jsonify({'error': 'HTML interface not found'}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'visiting-card-extractor',
        'version': '2.1.0',
        'features': ['user_auth', 'rls_security', 'supabase_integration']
    })

# ============ AUTHENTICATION ROUTES ============

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name', '')
    company = data.get('company', '')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required'}), 400
    
    result = auth_manager.register_user(email, password, full_name, company)
    return jsonify(result), 201 if result['success'] else 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required'}), 400
    
    # Since login_user now returns a Flask Response object directly, we can just return it
    return auth_manager.login_user(email, password)


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Logout user"""
    # Since logout_user now returns a Flask Response object directly, we can just return it
    return auth_manager.logout_user()

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current user information"""
    user = request.current_user
    stats = supabase_manager.get_user_stats(user['id'])
    return jsonify({'success': True, 'user': user, 'stats': stats})

# ============ CONTACT PROCESSING ROUTES ============
@app.route('/api/process-visiting-card', methods=['POST'])
@require_auth
def process_visiting_card():
    """Process uploaded visiting card image"""
    user_id = request.current_user['id']
    print(f"🔄 Processing visiting card for user: {user_id}")
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400
    
    file = request.files['image']
    
    # Validate file
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file'}), 400
    
    # Save temporarily
    filename = secure_filename(file.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{filename}")
    file.save(temp_path)
    
    try:
        print("🤖 Starting AI processing...")
        result = processor.process_visiting_card(temp_path)
        
        if result['success']:
            contact_data = result['contact_info']
            
            # Generate embedding for search
            searchable_text = processor.gpt_extractor._create_business_intelligence_text(contact_data)
            
            # Use the correct method from supabase_vector_store
            embedding = supabase_vector_store.get_embedding(searchable_text)
            
            # Store in Supabase
            contact_id = supabase_vector_store.add_contact(
                user_id=user_id,
                contact_data=contact_data,
                embedding=embedding or [],
                searchable_text=searchable_text
            )
            
            result['contact_id'] = contact_id
            print(f"✅ Contact stored: {contact_data.get('company', 'Unknown')}")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Processing error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)        

@app.route('/api/contacts', methods=['GET'])
@require_auth
def get_user_contacts():
    """Get all contacts for current user"""
    user_id = request.current_user['id']
    contacts = supabase_vector_store.get_all_contacts(user_id)
    return jsonify({
        'success': True,
        'contacts': contacts,
        'count': len(contacts)
    })

@app.route('/api/search-contacts', methods=['POST'])
@require_auth
def search_user_contacts():
    """Search contacts for current user"""
    user_id = request.current_user['id']
    data = request.get_json()
    query = data.get('query', '')
    limit = data.get('limit', 5)
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    try:
        # Generate query embedding using the correct method
        enhanced_query = supabase_vector_store._create_intelligent_query(query)
        query_embedding = supabase_vector_store.get_embedding(enhanced_query)
        
        # Search contacts
        results = supabase_vector_store.query_contacts(
            user_id=user_id,
            query=query,
            query_embedding=query_embedding,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        print(f"💥 Error searching contacts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/contacts/<contact_id>', methods=['DELETE'])
@require_auth
def delete_user_contact(contact_id):
    """Delete a specific contact"""
    user_id = request.current_user['id']
    success = supabase_vector_store.delete_contact(user_id, contact_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Contact deleted'})
    else:
        return jsonify({'success': False, 'error': 'Contact not found'}), 404

# ============ LEGACY COMPATIBILITY ============

@app.route('/api/query-contacts', methods=['POST'])
@require_auth
def legacy_query_contacts():
    """Legacy endpoint - redirects to search-contacts"""
    return search_user_contacts()

@app.route('/api/all-contacts', methods=['GET'])
@require_auth
def legacy_get_all_contacts():
    """Legacy endpoint - redirects to contacts"""
    return get_user_contacts()

@app.route('/api/stats', methods=['GET'])
@require_auth
def get_stats():
    """Get user statistics"""
    user_id = request.current_user['id']
    stats = supabase_manager.get_user_stats(user_id)
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/debug-contacts', methods=['GET'])
@require_auth
def debug_contacts():
    """Debug endpoint for contacts"""
    user_id = request.current_user['id']
    contacts = supabase_vector_store.get_all_contacts(user_id)
    
    debug_info = {
        'user_id': user_id,
        'total_contacts': len(contacts),
        'contacts': [
            {
                'id': contact.get('id'),
                'company': contact.get('contact_data', {}).get('company'),
                'name': contact.get('contact_data', {}).get('name')
            }
            for contact in contacts
        ]
    }
    
    return jsonify({'success': True, 'debug_info': debug_info})

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/debug-search-flow', methods=['POST'])
@require_auth
def debug_search_flow():
    user_id = request.current_user['id']
    query = request.get_json().get('query', 'real estate')
    
    # Test the complete flow
    enhanced_query = supabase_vector_store._create_intelligent_query(query)
    query_embedding = supabase_vector_store.get_embedding(enhanced_query)
    
    # Check what semantic search returns
    semantic_results = supabase_manager.semantic_search_contacts(user_id, query_embedding, 5)
    
    return jsonify({
        'original_query': query,
        'enhanced_query': enhanced_query,
        'embedding_length': len(query_embedding) if query_embedding else 0,
        'semantic_results_count': len(semantic_results),
        'semantic_results': semantic_results[:2]  # First 2 for debugging
    })

if __name__ == '__main__':
    print("🚀 Starting Secure Visiting Card Extractor...")
    print("Available endpoints:")
    print("  GET  /                          - Web interface")
    print("  POST /api/auth/register         - User registration")
    print("  POST /api/auth/login            - User login")
    print("  POST /api/process-visiting-card - Process image")
    print("  GET  /api/contacts              - Get contacts")
    print("  POST /api/search-contacts       - Search contacts")
    print("  GET  /api/health                - Health check")
    
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)