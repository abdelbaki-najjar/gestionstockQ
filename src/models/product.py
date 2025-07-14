from datetime import datetime
from . import db

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=10)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    supplier = db.relationship('Supplier', backref='products')
    order_items = db.relationship('OrderItem', backref='product')
    stock_movements = db.relationship('StockMovement', backref='product')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'reference': self.reference,
            'unit_price': self.unit_price,
            'stock_quantity': self.stock_quantity,
            'min_stock_level': self.min_stock_level,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_low_stock': self.stock_quantity <= self.min_stock_level
        }
    
    def __repr__(self):
        return f'<Product {self.name}>'

