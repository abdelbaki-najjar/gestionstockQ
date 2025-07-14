from flask import Blueprint, request, jsonify
from src.models import db, Product, Supplier, StockMovement, MovementType
from datetime import datetime

products_bp = Blueprint('products', __name__)

@products_bp.route('/products', methods=['GET'])
def get_products():
    """Récupère tous les produits avec filtres optionnels"""
    try:
        # Paramètres de filtrage
        category = request.args.get('category')
        supplier_id = request.args.get('supplier_id')
        low_stock = request.args.get('low_stock', 'false').lower() == 'true'
        search = request.args.get('search', '').strip()
        
        # Construction de la requête
        query = Product.query
        
        if category:
            query = query.filter(Product.category.ilike(f'%{category}%'))
        
        if supplier_id:
            query = query.filter(Product.supplier_id == supplier_id)
        
        if search:
            query = query.filter(
                db.or_(
                    Product.name.ilike(f'%{search}%'),
                    Product.reference.ilike(f'%{search}%'),
                    Product.description.ilike(f'%{search}%')
                )
            )
        
        products = query.all()
        
        # Filtrer les produits en stock bas si demandé
        if low_stock:
            products = [p for p in products if p.stock_quantity <= p.min_stock_level]
        
        return jsonify({
            'success': True,
            'products': [product.to_dict() for product in products],
            'count': len(products)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Récupère un produit spécifique"""
    try:
        product = Product.query.get_or_404(product_id)
        return jsonify({
            'success': True,
            'product': product.to_dict()
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products', methods=['POST'])
def create_product():
    """Crée un nouveau produit"""
    try:
        data = request.get_json()
        
        # Validation des données requises
        required_fields = ['name', 'category', 'reference', 'unit_price']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Le champ {field} est requis'}), 400
        
        # Vérifier l'unicité de la référence
        existing_product = Product.query.filter_by(reference=data['reference']).first()
        if existing_product:
            return jsonify({'success': False, 'error': 'Cette référence existe déjà'}), 400
        
        # Vérifier que le fournisseur existe si spécifié
        if data.get('supplier_id'):
            supplier = Supplier.query.get(data['supplier_id'])
            if not supplier:
                return jsonify({'success': False, 'error': 'Fournisseur introuvable'}), 400
        
        # Créer le produit
        product = Product(
            name=data['name'],
            description=data.get('description', ''),
            category=data['category'],
            reference=data['reference'],
            unit_price=float(data['unit_price']),
            stock_quantity=int(data.get('stock_quantity', 0)),
            min_stock_level=int(data.get('min_stock_level', 10)),
            supplier_id=data.get('supplier_id')
        )
        
        db.session.add(product)
        db.session.commit()
        
        # Créer un mouvement de stock initial si nécessaire
        if product.stock_quantity > 0:
            movement = StockMovement.create_movement(
                product=product,
                movement_type=MovementType.IN,
                quantity=product.stock_quantity,
                reason="Stock initial",
                created_by="System"
            )
            db.session.add(movement)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'product': product.to_dict(),
            'message': 'Produit créé avec succès'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Met à jour un produit"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        
        # Vérifier l'unicité de la référence si elle change
        if 'reference' in data and data['reference'] != product.reference:
            existing_product = Product.query.filter_by(reference=data['reference']).first()
            if existing_product:
                return jsonify({'success': False, 'error': 'Cette référence existe déjà'}), 400
        
        # Vérifier que le fournisseur existe si spécifié
        if 'supplier_id' in data and data['supplier_id']:
            supplier = Supplier.query.get(data['supplier_id'])
            if not supplier:
                return jsonify({'success': False, 'error': 'Fournisseur introuvable'}), 400
        
        # Mettre à jour les champs
        updatable_fields = ['name', 'description', 'category', 'reference', 'unit_price', 'min_stock_level', 'supplier_id']
        for field in updatable_fields:
            if field in data:
                setattr(product, field, data[field])
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'product': product.to_dict(),
            'message': 'Produit mis à jour avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Supprime un produit"""
    try:
        product = Product.query.get_or_404(product_id)
        
        # Vérifier s'il y a des commandes liées
        if product.order_items:
            return jsonify({
                'success': False, 
                'error': 'Impossible de supprimer ce produit car il est lié à des commandes'
            }), 400
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Produit supprimé avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products/<int:product_id>/stock', methods=['POST'])
def adjust_stock(product_id):
    """Ajuste le stock d'un produit"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        
        movement_type = data.get('movement_type')
        quantity = data.get('quantity')
        reason = data.get('reason', '')
        created_by = data.get('created_by', 'User')
        
        if not movement_type or quantity is None:
            return jsonify({'success': False, 'error': 'Type de mouvement et quantité requis'}), 400
        
        # Convertir le type de mouvement
        try:
            movement_type_enum = MovementType(movement_type)
        except ValueError:
            return jsonify({'success': False, 'error': 'Type de mouvement invalide'}), 400
        
        # Créer le mouvement de stock
        movement = StockMovement.create_movement(
            product=product,
            movement_type=movement_type_enum,
            quantity=int(quantity),
            reason=reason,
            created_by=created_by
        )
        
        db.session.add(movement)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'product': product.to_dict(),
            'movement': movement.to_dict(),
            'message': 'Stock ajusté avec succès'
        })
    
    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products/<int:product_id>/movements', methods=['GET'])
def get_product_movements(product_id):
    """Récupère l'historique des mouvements de stock d'un produit"""
    try:
        product = Product.query.get_or_404(product_id)
        movements = StockMovement.query.filter_by(product_id=product_id).order_by(StockMovement.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'product_name': product.name,
            'movements': [movement.to_dict() for movement in movements],
            'count': len(movements)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/products/categories', methods=['GET'])
def get_categories():
    """Récupère toutes les catégories de produits"""
    try:
        categories = db.session.query(Product.category).distinct().all()
        categories_list = [cat[0] for cat in categories if cat[0]]
        
        return jsonify({
            'success': True,
            'categories': sorted(categories_list)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

