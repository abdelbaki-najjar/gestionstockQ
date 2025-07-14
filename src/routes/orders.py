from flask import Blueprint, request, jsonify
from src.models import db, Order, OrderItem, OrderStatus, OrderType, Product, Supplier, StockMovement, MovementType
from datetime import datetime
import uuid

orders_bp = Blueprint('orders', __name__)

def generate_order_number(order_type):
    """Génère un numéro de commande unique"""
    prefix = "ACH" if order_type == OrderType.PURCHASE else "VTE"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"

@orders_bp.route('/orders', methods=['GET'])
def get_orders():
    """Récupère toutes les commandes avec filtres optionnels"""
    try:
        # Paramètres de filtrage
        order_type = request.args.get('order_type')
        status = request.args.get('status')
        supplier_id = request.args.get('supplier_id')
        search = request.args.get('search', '').strip()
        
        # Construction de la requête
        query = Order.query
        
        if order_type:
            try:
                order_type_enum = OrderType(order_type)
                query = query.filter(Order.order_type == order_type_enum)
            except ValueError:
                return jsonify({'success': False, 'error': 'Type de commande invalide'}), 400
        
        if status:
            try:
                status_enum = OrderStatus(status)
                query = query.filter(Order.status == status_enum)
            except ValueError:
                return jsonify({'success': False, 'error': 'Statut invalide'}), 400
        
        if supplier_id:
            query = query.filter(Order.supplier_id == supplier_id)
        
        if search:
            query = query.filter(
                db.or_(
                    Order.order_number.ilike(f'%{search}%'),
                    Order.customer_name.ilike(f'%{search}%'),
                    Order.notes.ilike(f'%{search}%')
                )
            )
        
        orders = query.order_by(Order.order_date.desc()).all()
        
        return jsonify({
            'success': True,
            'orders': [order.to_dict() for order in orders],
            'count': len(orders)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Récupère une commande spécifique"""
    try:
        order = Order.query.get_or_404(order_id)
        return jsonify({
            'success': True,
            'order': order.to_dict()
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders', methods=['POST'])
def create_order():
    """Crée une nouvelle commande"""
    try:
        data = request.get_json()
        
        # Validation des données requises
        order_type = data.get('order_type')
        if not order_type:
            return jsonify({'success': False, 'error': 'Le type de commande est requis'}), 400
        
        try:
            order_type_enum = OrderType(order_type)
        except ValueError:
            return jsonify({'success': False, 'error': 'Type de commande invalide'}), 400
        
        # Validation spécifique selon le type
        if order_type_enum == OrderType.PURCHASE:
            if not data.get('supplier_id'):
                return jsonify({'success': False, 'error': 'Le fournisseur est requis pour une commande d\'achat'}), 400
            
            supplier = Supplier.query.get(data['supplier_id'])
            if not supplier:
                return jsonify({'success': False, 'error': 'Fournisseur introuvable'}), 400
        
        # Créer la commande
        order = Order(
            order_number=generate_order_number(order_type_enum),
            order_type=order_type_enum,
            supplier_id=data.get('supplier_id'),
            customer_name=data.get('customer_name', ''),
            customer_email=data.get('customer_email', ''),
            customer_phone=data.get('customer_phone', ''),
            expected_delivery_date=datetime.fromisoformat(data['expected_delivery_date']) if data.get('expected_delivery_date') else None,
            notes=data.get('notes', '')
        )
        
        db.session.add(order)
        db.session.flush()  # Pour obtenir l'ID de la commande
        
        # Ajouter les articles de commande
        items_data = data.get('items', [])
        if not items_data:
            return jsonify({'success': False, 'error': 'Au moins un article est requis'}), 400
        
        for item_data in items_data:
            product = Product.query.get(item_data.get('product_id'))
            if not product:
                return jsonify({'success': False, 'error': f'Produit {item_data.get("product_id")} introuvable'}), 400
            
            # Vérifier le stock pour les ventes
            if order_type_enum == OrderType.SALE:
                if product.stock_quantity < item_data.get('quantity', 0):
                    return jsonify({
                        'success': False, 
                        'error': f'Stock insuffisant pour {product.name} (disponible: {product.stock_quantity})'
                    }), 400
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=item_data['product_id'],
                quantity=item_data['quantity'],
                unit_price=item_data.get('unit_price', product.unit_price)
            )
            order_item.calculate_total_price()
            db.session.add(order_item)
        
        # Calculer le total de la commande
        order.calculate_total()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order': order.to_dict(),
            'message': 'Commande créée avec succès'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    """Met à jour une commande"""
    try:
        order = Order.query.get_or_404(order_id)
        data = request.get_json()
        
        # Vérifier que la commande peut être modifiée
        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            return jsonify({
                'success': False, 
                'error': 'Impossible de modifier une commande livrée ou annulée'
            }), 400
        
        # Mettre à jour les champs de base
        updatable_fields = [
            'customer_name', 'customer_email', 'customer_phone', 
            'expected_delivery_date', 'notes'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field == 'expected_delivery_date' and data[field]:
                    setattr(order, field, datetime.fromisoformat(data[field]))
                else:
                    setattr(order, field, data[field])
        
        order.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order': order.to_dict(),
            'message': 'Commande mise à jour avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    """Met à jour le statut d'une commande"""
    try:
        order = Order.query.get_or_404(order_id)
        data = request.get_json()
        
        new_status = data.get('status')
        if not new_status:
            return jsonify({'success': False, 'error': 'Le statut est requis'}), 400
        
        try:
            new_status_enum = OrderStatus(new_status)
        except ValueError:
            return jsonify({'success': False, 'error': 'Statut invalide'}), 400
        
        old_status = order.status
        order.status = new_status_enum
        
        # Actions spéciales selon le nouveau statut
        if new_status_enum == OrderStatus.DELIVERED:
            order.actual_delivery_date = datetime.utcnow()
            
            # Mettre à jour le stock selon le type de commande
            for item in order.order_items:
                if order.order_type == OrderType.PURCHASE:
                    # Commande d'achat : ajouter au stock
                    movement = StockMovement.create_movement(
                        product=item.product,
                        movement_type=MovementType.IN,
                        quantity=item.quantity,
                        reason=f"Réception commande {order.order_number}",
                        reference_type="order",
                        reference_id=order.id,
                        unit_cost=item.unit_price,
                        created_by="System"
                    )
                    db.session.add(movement)
                
                elif order.order_type == OrderType.SALE:
                    # Commande de vente : retirer du stock
                    movement = StockMovement.create_movement(
                        product=item.product,
                        movement_type=MovementType.OUT,
                        quantity=item.quantity,
                        reason=f"Vente commande {order.order_number}",
                        reference_type="order",
                        reference_id=order.id,
                        created_by="System"
                    )
                    db.session.add(movement)
        
        order.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order': order.to_dict(),
            'message': f'Statut mis à jour de {old_status.value} à {new_status_enum.value}'
        })
    
    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Supprime une commande"""
    try:
        order = Order.query.get_or_404(order_id)
        
        # Vérifier que la commande peut être supprimée
        if order.status == OrderStatus.DELIVERED:
            return jsonify({
                'success': False, 
                'error': 'Impossible de supprimer une commande livrée'
            }), 400
        
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Commande supprimée avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders/<int:order_id>/items', methods=['POST'])
def add_order_item(order_id):
    """Ajoute un article à une commande"""
    try:
        order = Order.query.get_or_404(order_id)
        data = request.get_json()
        
        # Vérifier que la commande peut être modifiée
        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            return jsonify({
                'success': False, 
                'error': 'Impossible de modifier une commande livrée ou annulée'
            }), 400
        
        product = Product.query.get(data.get('product_id'))
        if not product:
            return jsonify({'success': False, 'error': 'Produit introuvable'}), 400
        
        # Vérifier le stock pour les ventes
        if order.order_type == OrderType.SALE:
            if product.stock_quantity < data.get('quantity', 0):
                return jsonify({
                    'success': False, 
                    'error': f'Stock insuffisant pour {product.name}'
                }), 400
        
        order_item = OrderItem(
            order_id=order.id,
            product_id=data['product_id'],
            quantity=data['quantity'],
            unit_price=data.get('unit_price', product.unit_price)
        )
        order_item.calculate_total_price()
        
        db.session.add(order_item)
        order.calculate_total()
        order.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order': order.to_dict(),
            'message': 'Article ajouté avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/orders/<int:order_id>/items/<int:item_id>', methods=['DELETE'])
def remove_order_item(order_id, item_id):
    """Supprime un article d'une commande"""
    try:
        order = Order.query.get_or_404(order_id)
        item = OrderItem.query.get_or_404(item_id)
        
        # Vérifier que l'article appartient à la commande
        if item.order_id != order.id:
            return jsonify({'success': False, 'error': 'Article non trouvé dans cette commande'}), 404
        
        # Vérifier que la commande peut être modifiée
        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            return jsonify({
                'success': False, 
                'error': 'Impossible de modifier une commande livrée ou annulée'
            }), 400
        
        db.session.delete(item)
        order.calculate_total()
        order.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order': order.to_dict(),
            'message': 'Article supprimé avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

