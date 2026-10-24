CREATE TABLE inventory.stock_items (
    book_id int primary key,
    quantity int not null default 0 check (quantity >= 0),
    reserved int not null default 0 check (reserved >= 0)
);

CREATE TABLE inventory.suppliers (
    id serial primary key,
    name varchar(32) not null
);

CREATE TABLE inventory.purchases (
    id serial primary key,
    supplier_id int not null,
    time timestamp not null default CURRENT_TIMESTAMP,
    total_cost int not null check (total_cost > 0),
    foreign key (supplier_id) references inventory.suppliers(id)
);

CREATE TABLE inventory.books_purchases (
    purchase_id int not null,
    book_id int not null,
    quantity int not null check (quantity > 0),
    primary key (purchase_id, book_id),
    foreign key (purchase_id) references inventory.purchases(id)
);

CREATE TABLE inventory.outbox (
    id uuid primary key default gen_random_uuid(),
    event_type varchar(128) not null,
    payload jsonb not null,
    created_at timestamp not null default CURRENT_TIMESTAMP,
    published_at timestamp,
    attempts int not null default 0
);

CREATE TABLE inventory.inbox (
    event_id uuid primary key,
    event_type varchar(128) not null,
    processed_at timestamp not null default CURRENT_TIMESTAMP
);
