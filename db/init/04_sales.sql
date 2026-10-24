CREATE TABLE sales.payment_methods (
    id serial primary key,
    name varchar(32) not null unique
);

CREATE TABLE sales.couriers (
    id serial primary key,
    name varchar(32) not null
);

CREATE TABLE sales.deliveries (
    id serial primary key,
    courier_id int not null,
    foreign key (courier_id) references sales.couriers(id)
);

CREATE TABLE sales.customers (
    id serial primary key,
    first_name varchar(32) not null,
    last_name varchar(32),
    birth_date date not null,
    phone varchar(32) not null unique,
    email varchar(64)
);

CREATE TABLE sales.orders (
    id serial primary key,
    customer_id int not null,
    payment_method_id int not null,
    delivery_id int,
    time timestamp not null default CURRENT_TIMESTAMP,
    total_cost int not null check (total_cost > 0),
    status varchar(32) not null default 'PENDING',
    foreign key (customer_id) references sales.customers(id),
    foreign key (payment_method_id) references sales.payment_methods(id),
    foreign key (delivery_id) references sales.deliveries(id)
);

CREATE TABLE sales.books_orders (
    order_id int not null,
    book_id int not null,
    quantity int not null check (quantity > 0),
    primary key (order_id, book_id),
    foreign key (order_id) references sales.orders(id)
);

-- Transaction Outbox: события атомарно с бизнес-данными
CREATE TABLE sales.outbox (
    id uuid primary key default gen_random_uuid(),
    event_type varchar(128) not null,
    payload jsonb not null,
    created_at timestamp not null default CURRENT_TIMESTAMP,
    published_at timestamp,
    attempts int not null default 0
);

-- Transaction Inbox: идемпотентная обработка входящих событий
CREATE TABLE sales.inbox (
    event_id uuid primary key,
    event_type varchar(128) not null,
    processed_at timestamp not null default CURRENT_TIMESTAMP
);
