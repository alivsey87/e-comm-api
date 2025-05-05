from __future__ import annotations

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey, Table, Column, String, DateTime, func, select
from marshmallow import ValidationError, fields
from typing import List
import os


# ======================= Initialization =======================

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+mysqlconnector://root:{os.environ.get('DB_PASSWORD')}@localhost/ecommerce_api'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)
ma = Marshmallow(app)


# ======================= Association Table =======================

order_product = Table(
    "order_product",
    Base.metadata,
    Column('order_id', ForeignKey('orders.id'), primary_key=True),
    Column('product_id', ForeignKey('products.id'), primary_key=True)
)


# ======================= Database Models =======================

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    orders: Mapped[List['Order']] = relationship('Order', back_populates='user')
    
    
class Order(Base):
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    order_date: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    user: Mapped[User] = relationship('User', back_populates='orders') 
    products: Mapped[List['Product']] = relationship('Product', secondary=order_product, back_populates='orders')
    
    
class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)   
    orders: Mapped[List['Order']] = relationship('Order', secondary=order_product, back_populates='products')    



# ======================= Schemas =======================

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        
        
class OrderSchema(ma.SQLAlchemyAutoSchema):
    user_id = fields.Integer(required=True)
    order_date = fields.DateTime(required=False)
    
    class Meta:
        model = Order 
        include_fk = True 
        
        
class ProductSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Product  
        
        
user_schema = UserSchema() 
users_schema = UserSchema(many=True)
 
order_schema = OrderSchema()  
orders_schema = OrderSchema(many=True)

product_schema = ProductSchema() 
products_schema = ProductSchema(many=True)                      


# ======================= Routes/Endpoints =======================


#    ------------ USERS ------------


# POST /users (CREATE)
@app.route('/users', methods=['POST'])
def create_user():
    try:
        user_data = user_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    new_user = User(name=user_data['name'], address=user_data['address'], email=user_data['email'])
    db.session.add(new_user)
    db.session.commit()
    
    return user_schema.jsonify(new_user), 201

# GET /users (READ)
@app.route('/users', methods=['GET'])
def get_users():
    query = select(User)
    users = db.session.execute(query).scalars().all()
    
    return users_schema.jsonify(users), 200

# GET /users/<id> (READ)
@app.route('/users/<int:id>', methods=['GET'])
def get_user(id):
    user = db.session.get(User, id)
    
    return user_schema.jsonify(user), 200

# PUT /users/<id> (UPDATE)
@app.route('/users/<int:id>', methods=['PUT'])
def update_user(id):
    user = db.session.get(User, id)
    
    if not user:
        return jsonify({'message': 'Invalid user id'}), 400
    
    try:
        user_data = user_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    user.name = user_data['name']
    user.address = user_data['address']
    user.email = user_data['email']
    
    db.session.commit()
    return user_schema.jsonify(user), 200

# DELETE /users/<id>
@app.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    user = db.session.get(User, id)
    
    if not user:
        return jsonify({'message': 'Invalid user id'}), 400
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'Successfully deleted user {id}'}, 200)
    
    
#    ------------ ORDERS ------------  


# POST /orders (CREATE)
@app.route('/orders', methods=['POST'])
def create_order():
    try:
        order_data = order_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    user = db.session.get(User, order_data['user_id'])
    if not user:
        return jsonify({'message': 'Invalid user_id'}), 400
    
    new_order = Order(
        order_date=order_data.get('order_date'), 
        user_id=order_data['user_id']
    )
    db.session.add(new_order)
    db.session.commit()
    return order_schema.jsonify(new_order), 201

# GET /orders/user/<user_id> (READ) -- All orders for a user
@app.route('/orders/user/<int:user_id>', methods=['GET'])
def get_orders(user_id):
    orders = db.session.query(Order).filter_by(user_id=user_id).all()
    
    if not orders:
        return jsonify({"message": "No orders found for this user."}), 404
    
    return orders_schema.jsonify(orders), 200

# GET /orders/<order_id>/products (READ) -- All products for an order
@app.route('/orders/<int:order_id>/products', methods=['GET'])
def get_products_for_order(order_id):
    order =db.session.get(Order, order_id)
    
    if not order:
        return jsonify({'message': 'Order not found'}), 404
    
    products = order.products
    
    if not order.products:
        return jsonify({'message': f'No products found for this order'}), 404
    
    return products_schema.jsonify(products), 200

# PUT /orders/<order_id>/add_product/<product_id> (UPDATE) -- Add product to order
@app.route('/orders/<int:order_id>/add_product/<int:product_id>', methods=['PUT'])
def add_prod_to_order(order_id, product_id):
    order = db.session.get(Order, order_id)
    product = db.session.get(Product, product_id)
    
    if not order:
        return jsonify({'message': 'Invalid order ID'}), 400
    if not product:
        return jsonify({'message': 'Invalid product ID'}), 400
    
    if product in order.products:
        return jsonify({'message': 'Product already exists in the order'}), 400
    
    order.products.append(product)
    
    db.session.commit()
    return order_schema.jsonify(order), 200

# DELETE /orders/<order_id>/remove_product -- Remove product from order
@app.route('/orders/<int:order_id>/remove_product/<int:product_id>', methods=['DELETE'])
def remove_prod_from_order(order_id, product_id):
    
    order = db.session.get(Order, order_id)
    product = db.session.get(Product, product_id)
    
    if not order:
        return jsonify({'message': 'Invalid order ID'}), 400
    if not product:
        return jsonify({'message': 'Invalid product ID'}), 400
    
    if product not in order.products:
        return jsonify({'message': 'Product not found in the order'}), 404
    
    order.products.remove(product)
    
    db.session.commit()
    return jsonify({'message': f'Product {product_id} removed from order {order_id}'}), 200  


#    ------------ PRODUCTS ------------ 


# POST /products (CREATE)
@app.route('/products', methods=['POST'])
def create_product():
    try:
        product_data = product_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    new_product = Product(product_name=product_data['product_name'], price=product_data['price'])
    db.session.add(new_product)
    db.session.commit()
    
    return product_schema.jsonify(new_product), 201

# GET /products (READ)
@app.route('/products', methods=['GET'])
def get_products():
    query = select(Product)
    products = db.session.execute(query).scalars().all()
    
    return products_schema.jsonify(products), 200

# GET /products/<id> (READ)
@app.route('/products/<int:id>', methods=['GET'])
def get_product(id):
    product = db.session.get(Product, id)
    
    return product_schema.jsonify(product), 200

# PUT /products/<id> (UPDATE)
@app.route('/products/<int:id>', methods=['PUT'])
def update_product(id):
    product = db.session.get(Product, id)
    
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    try:
        product_data = product_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    product.product_name = product_data['product_name']
    product.price = product_data['price']
    
    db.session.commit()
    return product_schema.jsonify(product), 200

# DELETE /products/<id>
@app.route('/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    product = db.session.get(Product, id)
    
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    if product.orders:
        return jsonify({'message': 'Cannot delete product because it is associated with orders'}), 400
    
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': f'Successfully deleted product {id}'}, 200)



# ======================= Run server! =======================


if __name__ == "__main__":
    
    with app.app_context():
        db.create_all()
        
    app.run(debug=True)