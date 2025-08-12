from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from auth_manager import AuthManager, require_auth
from supabase_config import SupabaseManager, SupabaseVectorStore
from main import VisitingCardProcessor
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Initialize managers
auth_manager = AuthManager()
supabase_manager = SupabaseManager()
processor = VisitingCardProcessor()

# Replace ChromaDB with Supabase for multi-user support
supabase_vector_store = SupabaseVectorStore(supabase_manager)

# Configuration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============ PUBLIC ROUTES ============

@app.route('/')
def index():
    """Serve the main HTML page with authentication"""
    try:
        with open('secure_index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'secure_index.html not found'}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Public health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'visiting-card-extractor',
        'version': '2.0.0',
        'features': ['user_auth', 'rls_security', 'supabase_integration']
    })

# ============ AUTHENTICATION ROUTES ============

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        full_name = data.get('full_name', '')
        company = data.get('company', '')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        result = auth_manager.register_user(email, password, full_name, company)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        result = auth_manager.login_user(email, password)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Logout user"""
    try:
        result = auth_manager.logout_user()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current user information"""
    try:
        user = request.current_user
        
        # Get additional user stats
        stats = supabase_manager.get_user_stats(user['id'])
        
        return jsonify({
            'success': True,
            'user': user,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============ SECURE CONTACT PROCESSING ROUTES ============

@app.route('/api/process-visiting-card', methods=['POST'])
@require_auth
def process_visiting_card():
    """Process uploaded visiting card image (USER-SPECIFIC)"""
    user_id = request.current_user['id']
    print(f"🔄 Processing visiting card for user: {user_id}")
    
    try:
        # Check if file is in request
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400
        
        file = request.files['image']
        
        # Read file content to check actual size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        print(f"📄 File received: {file.filename}")
        print(f"📏 File size: {file_size} bytes")
        
        if file.filename == '' or file_size == 0:
            return jsonify({'success': False, 'error': 'No file selected or file is empty'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Unsupported file format'}), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{filename}")
        file.save(temp_path)
        
        try:
            print("🤖 Starting AI processing...")
            # Process the image with business intelligence
            result = processor.process_visiting_card(temp_path)
            
            if result['success']:
                # Store in Supabase with user association
                contact_data = result['contact_info']
                
                # Generate embedding for semantic search
                searchable_text = processor.gpt_extractor._create_business_intelligence_text(contact_data)
                embedding = processor.vector_db._get_embedding(searchable_text)
                
                # Store in Supabase with RLS protection
                contact_id = supabase_vector_store.add_contact(
                    user_id=user_id,
                    contact_data=contact_data,
                    embedding=embedding or [],
                    searchable_text=searchable_text
                )
                
                result['contact_id'] = contact_id
                print(f"✅ Contact stored for user {user_id}: {contact_data.get('company', 'Unknown')}")
            
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return jsonify(result)
            
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
            
    except Exception as e:
        print(f"💥 Processing error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/contacts', methods=['GET'])
@require_auth
def get_user_contacts():
    """Get all contacts for current user (RLS PROTECTED)"""
    user_id = request.current_user['id']
    print(f"📇 Getting contacts for user: {user_id}")
    
    try:
        contacts = supabase_vector_store.get_all_contacts(user_id)
        
        return jsonify({
            'success': True,
            'contacts': contacts,
            'count': len(contacts),
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"💥 Error getting contacts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search-contacts', methods=['POST'])
@require_auth
def search_user_contacts():
    """Search contacts for current user (RLS PROTECTED)"""
    user_id = request.current_user['id']
    
    try:
        data = request.get_json()
        query = data.get('query', '')
        limit = data.get('limit', 5)
        
        if not query:
            return jsonify({'success': False, 'error': 'Query is required'}), 400
        
        print(f"🔍 Searching contacts for user {user_id}: '{query}'")
        
        # Generate query embedding for semantic search
        enhanced_query = processor.vector_db._create_intelligent_query(query)
        query_embedding = processor.vector_db._get_embedding(enhanced_query)
        
        # Search user's contacts only (RLS enforced)
        results = supabase_vector_store.query_contacts(
            user_id=user_id,
            query=query,
            query_embedding=query_embedding,
            limit=limit
        )
        
        print(f"✅ Found {len(results)} contacts for user {user_id}")
        
        return jsonify({
            'success': True,
            'results': results,
            'query': query,
            'count': len(results),
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"💥 Search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/contacts/<contact_id>', methods=['DELETE'])
@require_auth
def delete_user_contact(contact_id):
    """Delete a specific contact (RLS PROTECTED)"""
    user_id = request.current_user['id']
    
    try:
        success = supabase_vector_store.delete_contact(user_id, contact_id)
        
        if success:
            print(f"✅ Contact {contact_id} deleted by user {user_id}")
            return jsonify({
                'success': True,
                'message': 'Contact deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Contact not found or unauthorized'
            }), 404
            
    except Exception as e:
        print(f"💥 Delete error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user/stats', methods=['GET'])
@require_auth
def get_user_statistics():
    """Get user statistics (RLS PROTECTED)"""
    user_id = request.current_user['id']
    
    try:
        stats = supabase_manager.get_user_stats(user_id)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f"💥 Stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ ADMIN ROUTES (Optional) ============

@app.route('/api/admin/users', methods=['GET'])
@require_auth
def admin_get_users():
    """Admin: Get all users (requires admin role)"""
    # This would require additional role checking
    user = request.current_user
    
    if user.get('role') != 'admin':
        return jsonify({
            'success': False,
            'error': 'Admin access required'
        }), 403
    
    # Admin functionality would go here
    return jsonify({
        'success': True,
        'message': 'Admin functionality not implemented yet'
    })

# ============ ERROR HANDLERS ============

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({
        'success': False,
        'error': 'Unauthorized access',
        'code': 401
    }), 401

@app.errorhandler(403)
def forbidden(error):
    return jsonify({
        'success': False,
        'error': 'Forbidden access',
        'code': 403
    }), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'code': 404
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'code': 500
    }), 500

if __name__ == '__main__':
    print("🚀 Starting Secure Visiting Card Extractor...")
    print("🔐 Features: User Authentication, RLS Security, Supabase Integration")
    print("Available endpoints:")
    print("  GET  /                          - Secure web interface")
    print("  POST /api/auth/register         - User registration")
    print("  POST /api/auth/login            - User login")
    print("  POST /api/auth/logout           - User logout")
    print("  GET  /api/auth/me               - Current user info")
    print("  POST /api/process-visiting-card - Process image (auth required)")
    print("  GET  /api/contacts              - Get user contacts (auth required)")
    print("  POST /api/search-contacts       - Search contacts (auth required)")
    print("  DELETE /api/contacts/<id>       - Delete contact (auth required)")
    print("  GET  /api/user/stats            - User statistics (auth required)")
    print("  GET  /api/health                - Health check")
    
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)