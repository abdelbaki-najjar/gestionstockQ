from datetime import datetime
from enum import Enum
from . import db

class MovementType(Enum):
    IN = "in"           # Entrée de stock
    OUT = "out"         # Sortie de stock
    ADJUSTMENT = "adjustment"  # Ajustement d'inventaire
    RETURN = "return"   # Retour

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    movement_type = db.Column(db.Enum(MovementType), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    previous_stock = db.Column(db.Integer, nullable=False)
    new_stock = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float)  # Coût unitaire lors du mouvement
    reference_type = db.Column(db.String(50))  # Type de référence (order, adjustment, etc.)
    reference_id = db.Column(db.Integer)  # ID de la référence (commande, etc.)
    reason = db.Column(db.String(200))  # Raison du mouvement
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))  # Utilisateur qui a effectué le mouvement
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'product_reference': self.product.reference if self.product else None,
            'movement_type': self.movement_type.value,
            'quantity': self.quantity,
            'previous_stock': self.previous_stock,
            'new_stock': self.new_stock,
            'unit_cost': self.unit_cost,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'reason': self.reason,
            'notes': self.notes,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def create_movement(product, movement_type, quantity, reason=None, reference_type=None, reference_id=None, unit_cost=None, created_by=None, notes=None):
        """Crée un mouvement de stock et met à jour le stock du produit"""
        previous_stock = product.stock_quantity
        
        if movement_type == MovementType.IN:
            new_stock = previous_stock + quantity
        elif movement_type == MovementType.OUT:
            new_stock = previous_stock - quantity
            if new_stock < 0:
                raise ValueError("Stock insuffisant pour effectuer cette sortie")
        elif movement_type == MovementType.ADJUSTMENT:
            new_stock = quantity  # Pour les ajustements, quantity représente le nouveau stock
            quantity = new_stock - previous_stock  # Calcul de la différence
        else:  # RETURN
            new_stock = previous_stock + quantity
        
        # Créer le mouvement
        movement = StockMovement(
            product_id=product.id,
            movement_type=movement_type,
            quantity=abs(quantity),
            previous_stock=previous_stock,
            new_stock=new_stock,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason,
            notes=notes,
            created_by=created_by
        )
        
        # Mettre à jour le stock du produit
        product.stock_quantity = new_stock
        product.updated_at = datetime.utcnow()
        
        return movement
    
    def __repr__(self):
        return f'<StockMovement {self.movement_type.value} {self.quantity} for {self.product.name if self.product else "Unknown"}>'

