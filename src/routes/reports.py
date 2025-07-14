from flask import Blueprint, request, jsonify
from src.models import db, Product, Order, OrderItem, OrderType, OrderStatus, StockMovement, Supplier
from datetime import datetime, timedelta
from sqlalchemy import func, and_

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Récupère les statistiques pour le tableau de bord"""
    try:
        # Statistiques générales
        total_products = Product.query.count()
        total_suppliers = Supplier.query.filter_by(is_active=True).count()
        
        # Produits en stock bas
        low_stock_products = Product.query.filter(
            Product.stock_quantity <= Product.min_stock_level
        ).count()
        
        # Commandes en cours
        pending_orders = Order.query.filter(
            Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.SHIPPED])
        ).count()
        
        # Valeur totale du stock
        total_stock_value = db.session.query(
            func.sum(Product.stock_quantity * Product.unit_price)
        ).scalar() or 0
        
        # Commandes du mois en cours
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_orders = Order.query.filter(
            Order.order_date >= start_of_month
        ).count()
        
        # Ventes du mois
        monthly_sales = db.session.query(
            func.sum(Order.total_amount)
        ).filter(
            and_(
                Order.order_type == OrderType.SALE,
                Order.order_date >= start_of_month,
                Order.status == OrderStatus.DELIVERED
            )
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_products': total_products,
                'total_suppliers': total_suppliers,
                'low_stock_products': low_stock_products,
                'pending_orders': pending_orders,
                'total_stock_value': round(total_stock_value, 2),
                'monthly_orders': monthly_orders,
                'monthly_sales': round(monthly_sales, 2)
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/reports/low-stock', methods=['GET'])
def get_low_stock_report():
    """Rapport des produits en stock bas"""
    try:
        products = Product.query.filter(
            Product.stock_quantity <= Product.min_stock_level
        ).order_by(Product.stock_quantity.asc()).all()
        
        return jsonify({
            'success': True,
            'products': [product.to_dict() for product in products],
            'count': len(products)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/reports/stock-movements', methods=['GET'])
def get_stock_movements_report():
    """Rapport des mouvements de stock"""
    try:
        # Paramètres de filtrage
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        product_id = request.args.get('product_id')
        movement_type = request.args.get('movement_type')
        
        query = StockMovement.query
        
        if start_date:
            query = query.filter(StockMovement.created_at >= datetime.fromisoformat(start_date))
        
        if end_date:
            query = query.filter(StockMovement.created_at <= datetime.fromisoformat(end_date))
        
        if product_id:
            query = query.filter(StockMovement.product_id == product_id)
        
        if movement_type:
            query = query.filter(StockMovement.movement_type == movement_type)
        
        movements = query.order_by(StockMovement.created_at.desc()).limit(1000).all()
        
        return jsonify({
            'success': True,
            'movements': [movement.to_dict() for movement in movements],
            'count': len(movements)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/reports/sales', methods=['GET'])
def get_sales_report():
    """Rapport des ventes"""
    try:
        # Paramètres de filtrage
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = Order.query.filter(
            Order.order_type == OrderType.SALE,
            Order.status == OrderStatus.DELIVERED
        )
        
        if start_date:
            query = query.filter(Order.order_date >= datetime.fromisoformat(start_date))
        
        if end_date:
            query = query.filter(Order.order_date <= datetime.fromisoformat(end_date))
        
        orders = query.order_by(Order.order_date.desc()).all()
        
        # Calculs des totaux
        total_sales = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        
        # Produits les plus vendus
        product_sales = db.session.query(
            Product.name,
            Product.reference,
            func.sum(OrderItem.quantity).label('total_quantity'),
            func.sum(OrderItem.total_price).label('total_amount')
        ).join(OrderItem).join(Order).filter(
            Order.order_type == OrderType.SALE,
            Order.status == OrderStatus.DELIVERED
        )
        
        if start_date:
            product_sales = product_sales.filter(Order.order_date >= datetime.fromisoformat(start_date))
        
        if end_date:
            product_sales = product_sales.filter(Order.order_date <= datetime.fromisoformat(end_date))
        
        top_products = product_sales.group_by(Product.id).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(10).all()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_sales': round(total_sales, 2),
                'total_orders': total_orders,
                'average_order_value': round(total_sales / total_orders if total_orders > 0 else 0, 2)
            },
            'orders': [order.to_dict() for order in orders],
            'top_products': [
                {
                    'name': product.name,
                    'reference': product.reference,
                    'quantity_sold': int(product.total_quantity),
                    'total_amount': round(float(product.total_amount), 2)
                }
                for product in top_products
            ]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/reports/purchases', methods=['GET'])
def get_purchases_report():
    """Rapport des achats"""
    try:
        # Paramètres de filtrage
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        supplier_id = request.args.get('supplier_id')
        
        query = Order.query.filter(Order.order_type == OrderType.PURCHASE)
        
        if start_date:
            query = query.filter(Order.order_date >= datetime.fromisoformat(start_date))
        
        if end_date:
            query = query.filter(Order.order_date <= datetime.fromisoformat(end_date))
        
        if supplier_id:
            query = query.filter(Order.supplier_id == supplier_id)
        
        orders = query.order_by(Order.order_date.desc()).all()
        
        # Calculs des totaux
        total_purchases = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        
        # Achats par fournisseur
        supplier_purchases = db.session.query(
            Supplier.name,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_amount')
        ).join(Order).filter(Order.order_type == OrderType.PURCHASE)
        
        if start_date:
            supplier_purchases = supplier_purchases.filter(Order.order_date >= datetime.fromisoformat(start_date))
        
        if end_date:
            supplier_purchases = supplier_purchases.filter(Order.order_date <= datetime.fromisoformat(end_date))
        
        top_suppliers = supplier_purchases.group_by(Supplier.id).order_by(
            func.sum(Order.total_amount).desc()
        ).limit(10).all()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_purchases': round(total_purchases, 2),
                'total_orders': total_orders,
                'average_order_value': round(total_purchases / total_orders if total_orders > 0 else 0, 2)
            },
            'orders': [order.to_dict() for order in orders],
            'top_suppliers': [
                {
                    'name': supplier.name,
                    'order_count': int(supplier.order_count),
                    'total_amount': round(float(supplier.total_amount), 2)
                }
                for supplier in top_suppliers
            ]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/reports/inventory-value', methods=['GET'])
def get_inventory_value_report():
    """Rapport de la valeur de l'inventaire"""
    try:
        # Valeur par catégorie
        category_values = db.session.query(
            Product.category,
            func.sum(Product.stock_quantity * Product.unit_price).label('total_value'),
            func.sum(Product.stock_quantity).label('total_quantity'),
            func.count(Product.id).label('product_count')
        ).group_by(Product.category).order_by(
            func.sum(Product.stock_quantity * Product.unit_price).desc()
        ).all()
        
        # Valeur par fournisseur
        supplier_values = db.session.query(
            Supplier.name,
            func.sum(Product.stock_quantity * Product.unit_price).label('total_value'),
            func.sum(Product.stock_quantity).label('total_quantity'),
            func.count(Product.id).label('product_count')
        ).join(Product).group_by(Supplier.id).order_by(
            func.sum(Product.stock_quantity * Product.unit_price).desc()
        ).all()
        
        # Valeur totale
        total_value = db.session.query(
            func.sum(Product.stock_quantity * Product.unit_price)
        ).scalar() or 0
        
        total_quantity = db.session.query(
            func.sum(Product.stock_quantity)
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'summary': {
                'total_value': round(total_value, 2),
                'total_quantity': int(total_quantity),
                'total_products': Product.query.count()
            },
            'by_category': [
                {
                    'category': cat.category,
                    'total_value': round(float(cat.total_value), 2),
                    'total_quantity': int(cat.total_quantity),
                    'product_count': int(cat.product_count)
                }
                for cat in category_values
            ],
            'by_supplier': [
                {
                    'supplier_name': sup.name,
                    'total_value': round(float(sup.total_value), 2),
                    'total_quantity': int(sup.total_quantity),
                    'product_count': int(sup.product_count)
                }
                for sup in supplier_values
            ]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

