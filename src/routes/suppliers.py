from flask import Blueprint, request, jsonify
from src.models import db, Supplier, Product
from datetime import datetime

suppliers_bp = Blueprint('suppliers', __name__)

@suppliers_bp.route('/suppliers', methods=['GET'])
def get_suppliers():
    """Récupère tous les fournisseurs avec filtres optionnels"""
    try:
        # Paramètres de filtrage
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        search = request.args.get('search', '').strip()
        
        # Construction de la requête
        query = Supplier.query
        
        if active_only:
            query = query.filter(Supplier.is_active == True)
        
        if search:
            query = query.filter(
                db.or_(
                    Supplier.name.ilike(f'%{search}%'),
                    Supplier.contact_person.ilike(f'%{search}%'),
                    Supplier.email.ilike(f'%{search}%'),
                    Supplier.city.ilike(f'%{search}%')
                )
            )
        
        suppliers = query.order_by(Supplier.name).all()
        
        return jsonify({
            'success': True,
            'suppliers': [supplier.to_dict() for supplier in suppliers],
            'count': len(suppliers)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@suppliers_bp.route('/suppliers/<int:supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    """Récupère un fournisseur spécifique"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        return jsonify({
            'success': True,
            'supplier': supplier.to_dict()
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@suppliers_bp.route('/suppliers', methods=['POST'])
def create_supplier():
    """Crée un nouveau fournisseur"""
    try:
        data = request.get_json()
        
        # Validation des données requises
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Le nom du fournisseur est requis'}), 400
        
        # Vérifier l'unicité du nom
        existing_supplier = Supplier.query.filter_by(name=data['name']).first()
        if existing_supplier:
            return jsonify({'success': False, 'error': 'Un fournisseur avec ce nom existe déjà'}), 400
        
        # Créer le fournisseur
        supplier = Supplier(
            name=data['name'],
            contact_person=data.get('contact_person', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            address=data.get('address', ''),
            city=data.get('city', ''),
            postal_code=data.get('postal_code', ''),
            country=data.get('country', ''),
            payment_terms=data.get('payment_terms', ''),
            notes=data.get('notes', ''),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'supplier': supplier.to_dict(),
            'message': 'Fournisseur créé avec succès'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@suppliers_bp.route('/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    """Met à jour un fournisseur"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        data = request.get_json()
        
        # Vérifier l'unicité du nom si il change
        if 'name' in data and data['name'] != supplier.name:
            existing_supplier = Supplier.query.filter_by(name=data['name']).first()
            if existing_supplier:
                return jsonify({'success': False, 'error': 'Un fournisseur avec ce nom existe déjà'}), 400
        
        # Mettre à jour les champs
        updatable_fields = [
            'name', 'contact_person', 'email', 'phone', 'address', 
            'city', 'postal_code', 'country', 'payment_terms', 'notes', 'is_active'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(supplier, field, data[field])
        
        supplier.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'supplier': supplier.to_dict(),
            'message': 'Fournisseur mis à jour avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@suppliers_bp.route('/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    """Supprime un fournisseur"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        
        # Vérifier s'il y a des produits liés
        products_count = Product.query.filter_by(supplier_id=supplier_id).count()
        if products_count > 0:
            return jsonify({
                'success': False, 
                'error': f'Impossible de supprimer ce fournisseur car il est lié à {products_count} produit(s)'
            }), 400
        
        # Vérifier s'il y a des commandes liées
        if supplier.orders:
            return jsonify({
                'success': False, 
                'error': 'Impossible de supprimer ce fournisseur car il est lié à des commandes'
            }), 400
        
        db.session.delete(supplier)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Fournisseur supprimé avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@suppliers_bp.route('/suppliers/<int:supplier_id>/products', methods=['GET'])
def get_supplier_products(supplier_id):
    """Récupère tous les produits d'un fournisseur"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        products = Product.query.filter_by(supplier_id=supplier_id).all()
        
        return jsonify({
            'success': True,
            'supplier_name': supplier.name,
            'products': [product.to_dict() for product in products],
            'count': len(products)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@suppliers_bp.route('/suppliers/<int:supplier_id>/toggle-status', methods=['POST'])
def toggle_supplier_status(supplier_id):
    """Active/désactive un fournisseur"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        supplier.is_active = not supplier.is_active
        supplier.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        status = "activé" if supplier.is_active else "désactivé"
        return jsonify({
            'success': True,
            'supplier': supplier.to_dict(),
            'message': f'Fournisseur {status} avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

