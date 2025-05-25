from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import bcrypt
from functools import wraps
import uuid

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'DRXENO'
app.config['MYSQL_DB'] = 'SistemaTallerMecanico'
app.config['MYSQL_PASSWORD'] = 'DrXeno79TESLA'
mysql = MySQL(app)

app.secret_key = 'mysecretkey'

# Decorador para requerir login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para restringir acceso por rol
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, inicia sesión primero.', 'danger')
                return redirect(url_for('login'))
            cur = mysql.connection.cursor()
            cur.execute('SELECT Role FROM Users WHERE IdUser = %s', (session['user_id'],))
            user_role = cur.fetchone()[0]
            if user_role not in roles:
                flash('Acceso denegado: No tienes permisos suficientes.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Ruta para login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        contrasena = request.form['contrasena']
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM Clientes WHERE email = %s", (email,))
        cliente = cursor.fetchone()
        cursor.close()
        if cliente and bcrypt.checkpw(contrasena.encode('utf-8'), cliente[8].encode('utf-8')):
            session['user_id'] = cliente[0]
            session['es_admin'] = cliente[7]
            if cliente[7] == 1:
                return redirect('/')
            else:
                return redirect('/vista_clientes')
        else:
            return render_template('/screens/login.html', error="Credenciales incorrectas")
    return render_template('/screens/login.html')
# Ruta para registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        email = request.form['email']
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        
        cur = mysql.connection.cursor()
        
        # Validar si el usuario o email ya existe
        cur.execute('SELECT IdUser FROM Users WHERE Username = %s OR Email = %s', (username, email))
        if cur.fetchone():
            flash('El nombre de usuario o correo ya está registrado.', 'danger')
            return redirect(url_for('register'))
        
        if role == 'client':
            nombre = request.form['nombre']
            apellido = request.form['apellido']
            telefono = request.form['telefono']
            direccion = request.form['direccion']
            
            # Insertar en Clientes
            cur.execute("INSERT INTO Clientes (Nombre, Apellido, Email, Telefono, Direccion, EstadoCuenta) VALUES (%s, %s, %s, %s, %s, %s)",
                        (nombre, apellido, email, telefono, direccion, 0))
            mysql.connection.commit()
            
            # Obtener el IdCliente recién creado
            cur.execute('SELECT IdCliente FROM Clientes WHERE Email = %s', (email,))
            id_reference = cur.fetchone()[0]
            
        elif role == 'admin':
            id_reference = 0
        
        # Insertar en Users
        cur.execute("INSERT INTO Users (Username, Password, Role, IdReference, Email) VALUES (%s, %s, %s, %s, %s)",
                    (username, hashed_password, role, id_reference, email))
        mysql.connection.commit()
        
        flash('Registro exitoso. Por favor, inicia sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('/screens/register.html')

# Ruta para logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('/login'))

# Ruta pública para ver trabajos realizados
@app.route('/trabajos')
def trabajos():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Trabajos WHERE Visible = 1')
    data = cur.fetchall()
    return render_template('/screens/trabajos.html', trabajos=data)

# Páginas protegidas
@app.route('/')
@login_required
@role_required('admin')
def index():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Clientes')
    data = cur.fetchall()
    return render_template('/screens/index.html', clientes=data)

@app.route('/clientes_vista')
@login_required
@role_required('client')
def clientes_vista():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Proyectos WHERE IdCliente = %s', (session['user_id'],))
    proyectos = cur.fetchall()
    return render_template('/vistas/vista_clientes.html', proyectos=proyectos)

@app.route('/admin/trabajos')
@login_required
@role_required('admin')
def admin_trabajos():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Trabajos')
    data = cur.fetchall()
    return render_template('/screens/admin_trabajos.html', trabajos=data)

@app.route('/admin/inventario')
@login_required
@role_required('admin')
def inventario():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Inventario')
    data = cur.fetchall()
    return render_template('/screens/inventario.html', inventario=data)

@app.route('/admin/proyectos')
@login_required
@role_required('admin')
def proyectos():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Proyectos')
    data = cur.fetchall()
    return render_template('/screens/proyectos.html', proyectos=data)

@app.route('/admin/citas')
@login_required
@role_required('admin')
def citas():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Citas')
    data = cur.fetchall()
    return render_template('/screens/citas.html', citas=data)

@app.route('/citas/solicitar', methods=['GET', 'POST'])
@login_required
@role_required('client')
def solicitar_cita():
    if request.method == 'POST':
        id_cliente = session['user_id']
        fecha_programada = request.form['fecha_programada']
        servicio = request.form['servicio']
        observaciones = request.form['observaciones']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Citas (IdCliente, FechaProgramada, Servicio, Estado, Observaciones) VALUES (%s, %s, %s, %s, %s)",
                    (id_cliente, fecha_programada, servicio, 'Programada', observaciones))
        mysql.connection.commit()
        flash('Cita solicitada correctamente', 'success')
        return redirect(url_for('clientes_vista'))
    return render_template('/screens/solicitar_cita.html')

# Guardar
@app.route('/add_cliente', methods=['POST'])
@login_required
@role_required('admin')
def add_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        email = request.form['email']
        telefono = request.form['telefono']
        direccion = request.form['direccion']
        estado_cuenta = request.form['estado_cuenta']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Clientes (Nombre, Apellido, Email, Telefono, Direccion, EstadoCuenta) VALUES (%s, %s, %s, %s, %s, %s)",
                    (nombre, apellido, email, telefono, direccion, estado_cuenta))
        mysql.connection.commit()
        flash('Cliente agregado correctamente', 'success')
        return redirect(url_for('index'))

@app.route('/add_trabajo', methods=['POST'])
@login_required
@role_required('admin')
def add_trabajo():
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_realizacion = request.form['fecha_realizacion']
        imagen = request.form['imagen']
        categoria = request.form['categoria']
        visible = request.form['visible']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Trabajos (Titulo, Descripcion, FechaRealizacion, Imagen, Categoria, Visible) VALUES (%s, %s, %s, %s, %s, %s)",
                    (titulo, descripcion, fecha_realizacion, imagen, categoria, visible))
        mysql.connection.commit()
        flash('Trabajo agregado correctamente', 'success')
        return redirect(url_for('admin_trabajos'))

@app.route('/add_inventario', methods=['POST'])
@login_required
@role_required('admin')
def add_inventario():
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        cantidad = request.form['cantidad']
        precio_unitario = request.form['precio_unitario']
        categoria = request.form['categoria']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Inventario (Nombre, Descripcion, Cantidad, PrecioUnitario, Categoria) VALUES (%s, %s, %s, %s, %s)",
                    (nombre, descripcion, cantidad, precio_unitario, categoria))
        mysql.connection.commit()
        flash('Item de inventario agregado correctamente', 'success')
        return redirect(url_for('inventario'))

@app.route('/add_proyecto', methods=['POST'])
@login_required
@role_required('admin')
def add_proyecto():
    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_inicio = request.form['fecha_inicio']
        fecha_fin_estimada = request.form['fecha_fin_estimada']
        estado = request.form['estado']
        costo_estimado = request.form['costo_estimado']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Proyectos (IdCliente, Titulo, Descripcion, FechaInicio, FechaFinEstimada, Estado, CostoEstimado) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (id_cliente, titulo, descripcion, fecha_inicio, fecha_fin_estimada, estado, costo_estimado))
        mysql.connection.commit()
        flash('Proyecto agregado correctamente', 'success')
        return redirect(url_for('proyectos'))

@app.route('/add_cita', methods=['POST'])
@login_required
@role_required('admin')
def add_cita():
    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        fecha_programada = request.form['fecha_programada']
        servicio = request.form['servicio']
        estado = request.form['estado']
        observaciones = request.form['observaciones']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Citas (IdCliente, FechaProgramada, Servicio, Estado, Observaciones) VALUES (%s, %s, %s, %s, %s)",
                    (id_cliente, fecha_programada, servicio, estado, observaciones))
        mysql.connection.commit()
        flash('Cita agregada correctamente', 'success')
        return redirect(url_for('citas'))

# Editar
@app.route('/edit_cliente/<id>')
@login_required
@role_required('admin')
def get_cliente(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Clientes WHERE IdCliente = %s', (id,))
    data = cur.fetchall()
    return render_template('/edit/edit_cliente.html', cliente=data[0])

@app.route('/edit_trabajo/<id>')
@login_required
@role_required('admin')
def get_trabajo(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Trabajos WHERE IdTrabajo = %s', (id,))
    data = cur.fetchall()
    return render_template('/edit/edit_trabajo.html', trabajo=data[0])

@app.route('/edit_inventario/<id>')
@login_required
@role_required('admin')
def get_inventario(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Inventario WHERE IdItem = %s', (id,))
    data = cur.fetchall()
    return render_template('/edit/edit_inventario.html', item=data[0])

@app.route('/edit_proyecto/<id>')
@login_required
@role_required('admin')
def get_proyecto(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Proyectos WHERE IdProyecto = %s', (id,))
    data = cur.fetchall()
    return render_template('/edit/edit_proyecto.html', proyecto=data[0])

@app.route('/edit_cita/<id>')
@login_required
@role_required('admin')
def get_cita(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM Citas WHERE IdCita = %s', (id,))
    data = cur.fetchall()
    return render_template('/edit/edit_cita.html', cita=data[0])

# Actualizar
@app.route('/update_cliente/<id>', methods=['POST'])
@login_required
@role_required('admin')
def update_cliente(id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        email = request.form['email']
        telefono = request.form['telefono']
        direccion = request.form['direccion']
        estado_cuenta = request.form['estado_cuenta']
        cur = mysql.connection.cursor()
        cur.execute("""UPDATE Clientes SET Nombre = %s, Apellido = %s, Email = %s, Telefono = %s, Direccion = %s, EstadoCuenta = %s WHERE IdCliente = %s""",
                    (nombre, apellido, email, telefono, direccion, estado_cuenta, id))
        mysql.connection.commit()
        flash('Cliente actualizado correctamente', 'success')
        return redirect(url_for('index'))

@app.route('/update_trabajo/<id>', methods=['POST'])
@login_required
@role_required('admin')
def update_trabajo(id):
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_realizacion = request.form['fecha_realizacion']
        imagen = request.form['imagen']
        categoria = request.form['categoria']
        visible = request.form['visible']
        cur = mysql.connection.cursor()
        cur.execute("""UPDATE Trabajos SET Titulo = %s, Descripcion = %s, FechaRealizacion = %s, Imagen = %s, Categoria = %s, Visible = %s WHERE IdTrabajo = %s""",
                    (titulo, descripcion, fecha_realizacion, imagen, categoria, visible, id))
        mysql.connection.commit()
        flash('Trabajo actualizado correctamente', 'success')
        return redirect(url_for('admin_trabajos'))

@app.route('/update_inventario/<id>', methods=['POST'])
@login_required
@role_required('admin')
def update_inventario(id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        cantidad = request.form['cantidad']
        precio_unitario = request.form['precio_unitario']
        categoria = request.form['categoria']
        cur = mysql.connection.cursor()
        cur.execute("""UPDATE Inventario SET Nombre = %s, Descripcion = %s, Cantidad = %s, PrecioUnitario = %s, Categoria = %s WHERE IdItem = %s""",
                    (nombre, descripcion, cantidad, precio_unitario, categoria, id))
        mysql.connection.commit()
        flash('Item de inventario actualizado correctamente', 'success')
        return redirect(url_for('inventario'))

@app.route('/update_proyecto/<id>', methods=['POST'])
@login_required
@role_required('admin')
def update_proyecto(id):
    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_inicio = request.form['fecha_inicio']
        fecha_fin_estimada = request.form['fecha_fin_estimada']
        estado = request.form['estado']
        costo_estimado = request.form['costo_estimado']
        cur = mysql.connection.cursor()
        cur.execute("""UPDATE Proyectos SET IdCliente = %s, Titulo = %s, Descripcion = %s, FechaInicio = %s, FechaFinEstimada = %s, Estado = %s, CostoEstimado = %s WHERE IdProyecto = %s""",
                    (id_cliente, titulo, descripcion, fecha_inicio, fecha_fin_estimada, estado, costo_estimado, id))
        mysql.connection.commit()
        flash('Proyecto actualizado correctamente', 'success')
        return redirect(url_for('proyectos'))

@app.route('/update_cita/<id>', methods=['POST'])
@login_required
@role_required('admin')
def update_cita(id):
    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        fecha_programada = request.form['fecha_programada']
        servicio = request.form['servicio']
        estado = request.form['estado']
        observaciones = request.form['observaciones']
        cur = mysql.connection.cursor()
        cur.execute("""UPDATE Citas SET IdCliente = %s, FechaProgramada = %s, Servicio = %s, Estado = %s, Observaciones = %s WHERE IdCita = %s""",
                    (id_cliente, fecha_programada, servicio, estado, observaciones, id))
        mysql.connection.commit()
        flash('Cita actualizada correctamente', 'success')
        return redirect(url_for('citas'))

# Eliminar
@app.route('/delete_cliente/<string:id>')
@login_required
@role_required('admin')
def delete_cliente(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM Clientes WHERE IdCliente = %s', (id,))
    mysql.connection.commit()
    flash('Cliente eliminado correctamente', 'success')
    return redirect(url_for('index'))

@app.route('/delete_trabajo/<string:id>')
@login_required
@role_required('admin')
def delete_trabajo(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM Trabajos WHERE IdTrabajo = %s', (id,))
    mysql.connection.commit()
    flash('Trabajo eliminado correctamente', 'success')
    return redirect(url_for('admin_trabajos'))

@app.route('/delete_inventario/<string:id>')
@login_required
@role_required('admin')
def delete_inventario(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM Inventario WHERE IdItem = %s', (id,))
    mysql.connection.commit()
    flash('Item de inventario eliminado correctamente', 'success')
    return redirect(url_for('inventario'))

@app.route('/delete_proyecto/<string:id>')
@login_required
@role_required('admin')
def delete_proyecto(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM Proyectos WHERE IdProyecto = %s', (id,))
    mysql.connection.commit()
    flash('Proyecto eliminado correctamente', 'success')
    return redirect(url_for('proyectos'))

@app.route('/delete_cita/<string:id>')
@login_required
@role_required('admin')
def delete_cita(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM Citas WHERE IdCita = %s', (id,))
    mysql.connection.commit()
    flash('Cita eliminada correctamente', 'success')
    return redirect(url_for('citas'))

if __name__ == '__main__':
    app.run(port=3000, debug=True)