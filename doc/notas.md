1. Dominio (Domain)
Definición

El dominio es la parte del sistema que representa el negocio o problema real que el software intenta modelar.

Contiene:

Entidades del negocio

Reglas de negocio

Comportamientos del sistema

Interfaces que describen cómo se interactúa con los datos

No contiene:

Base de datos

ORM

Frameworks

APIs

Detalles de infraestructura

La idea principal es que la lógica del negocio no dependa de ninguna tecnología.

Ejemplo de entidad del dominio
class Product:

    def __init__(self, id, name, barcode, price):
        self.id = id
        self.name = name
        self.barcode = barcode
        self.price = price

    def change_price(self, new_price):

        if new_price <= 0:
            raise ValueError("price must be positive")

        self.price = new_price

Esta clase pertenece al dominio porque:

representa un concepto real del negocio (producto)

contiene reglas de negocio (precio válido)

no depende de base de datos ni frameworks

Regla práctica para identificar el dominio

Si el código seguiría teniendo sentido aunque cambies la base de datos o el framework, entonces probablemente pertenece al dominio.

2. Connection Pooling
Qué es

El connection pooling es una técnica para reutilizar conexiones a la base de datos en lugar de abrir una nueva conexión cada vez que se ejecuta una consulta.

Abrir una conexión a la base de datos es costoso porque implica:

autenticación

handshake de red

asignación de recursos

Si cada consulta abre una conexión nueva, el sistema se vuelve lento.

Cómo funciona

En lugar de crear conexiones constantemente, se mantiene un pool de conexiones abiertas.

Connection Pool

C1
C2
C3
C4
C5

Flujo de uso:

Aplicación pide conexión
↓
Pool entrega una conexión existente
↓
Se ejecuta la consulta
↓
La conexión vuelve al pool

Esto mejora:

rendimiento

escalabilidad

estabilidad del sistema

Cómo se configura en SQLAlchemy
from sqlalchemy import create_engine

engine = create_engine(
    "mysql+pymysql://user:pass@localhost/kiosco",
    pool_size=10,
    max_overflow=20
)

Significado:

pool_size = 10
→ mantiene 10 conexiones abiertas

max_overflow = 20
→ puede crear hasta 20 conexiones extra si hay picos
3. Declarativo vs Imperativo en SQLAlchemy

Esto se refiere a cómo se mapea una clase Python a una tabla de base de datos.

Es decir, cómo se transforma:

Objeto Python ↔ Tabla SQL
Declarativo

En el estilo declarativo, la clase del modelo hereda del ORM.

Ejemplo:

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class Product(Base):

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    barcode = Column(String)

Características:

la clase depende de SQLAlchemy

la entidad está acoplada al ORM

mezcla negocio con persistencia

Dependencia resultante:

Product → SQLAlchemy
Imperativo

En el estilo imperativo, la entidad del dominio se define primero sin ORM, y el mapeo se realiza en otra parte.

Entidad del dominio:

class Product:

    def __init__(self, id, name, barcode):
        self.id = id
        self.name = name
        self.barcode = barcode

Mapping separado:

from sqlalchemy.orm import registry

mapper_registry = registry()

mapper_registry.map_imperatively(
    Product,
    products_table
)

Características:

el dominio queda independiente

el ORM vive en la capa de infraestructura

mejor separación de responsabilidades

Dependencia resultante:

Infrastructure → Domain
4. Por qué se llaman Declarativo e Imperativo
Declarativo

Se llama así porque se declara la estructura directamente en la clase.

La clase describe:

tabla
columnas
tipos
relaciones

Es una forma declarativa de describir el esquema.

Imperativo

Se llama así porque el mapping se realiza mediante instrucciones explícitas.

El código indica cómo mapear la clase a la tabla usando llamadas a funciones.

Ejemplo:

map_imperatively(Product, products_table)

Es un estilo imperativo, porque se ejecutan instrucciones que construyen el mapping.

5. Por qué es importante la diferencia

La diferencia afecta la arquitectura del sistema.

Declarativo

Ventajas:

más simple

menos código

Desventajas:

acopla el dominio al ORM

dificulta cambiar tecnología

mezcla negocio con persistencia

Imperativo

Ventajas:

dominio independiente

mejor arquitectura

facilita testing

permite cambiar base de datos o ORM

Arquitectura resultante:

Domain
   ↓
Repository Interface
   ↓
Infrastructure
   ↓
ORM / Database

El dominio queda aislado de detalles técnicos.

Resumen rápido
Dominio

Parte del sistema que contiene entidades y reglas del negocio, sin depender de tecnología.

Connection Pooling

Sistema que reutiliza conexiones a la base de datos para mejorar rendimiento y escalabilidad.

SQLAlchemy Declarativo

Las clases heredan del ORM y describen directamente la tabla.

SQLAlchemy Imperativo

Las entidades del dominio se mantienen limpias y el mapping ORM se define por separado.