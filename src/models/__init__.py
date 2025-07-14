from flask_sqlalchemy import SQLAlchemy

# Instance unique de SQLAlchemy
db = SQLAlchemy()

# Import de tous les modèles
from .product import Product
from .supplier import Supplier
from .order import Order, OrderItem, OrderStatus, OrderType
from .stock_movement import StockMovement, MovementType

# Export des modèles et enums
__all__ = [
    'db',
    'Product',
    'Supplier', 
    'Order',
    'OrderItem',
    'OrderStatus',
    'OrderType',
    'StockMovement',
    'MovementType'
]

