CREATE TABLE catalog.categories (
    id serial primary key,
    name varchar(32) not null unique
);

CREATE TABLE catalog.publishers (
    id serial primary key,
    name varchar(32) not null unique
);

CREATE TABLE catalog.books (
    id serial primary key,
    name varchar(128) not null,
    description text not null,
    category_id int not null,
    publisher_id int not null,
    isbn varchar(32) not null unique,
    age_limit varchar(4) not null,
    publication_date char(4) not null,
    pages_number int not null check (pages_number > 0),
    weight int not null check (weight > 0),
    price int not null check (price > 0),
    foreign key (category_id) references catalog.categories(id),
    foreign key (publisher_id) references catalog.publishers(id)
);

CREATE TABLE catalog.genres (
    id serial primary key,
    name varchar(32) not null unique
);

CREATE TABLE catalog.books_genres (
    book_id int not null,
    genre_id int not null,
    primary key (book_id, genre_id),
    foreign key (book_id) references catalog.books(id) on delete cascade,
    foreign key (genre_id) references catalog.genres(id)
);

CREATE TABLE catalog.authors (
    id serial primary key,
    first_name varchar(32) not null,
    last_name varchar(32)
);

CREATE TABLE catalog.books_authors (
    book_id int not null,
    author_id int not null,
    primary key (book_id, author_id),
    foreign key (book_id) references catalog.books(id) on delete cascade,
    foreign key (author_id) references catalog.authors(id)
);

CREATE TABLE catalog.reviews (
    id serial primary key,
    book_id int not null,
    customer_id int not null,
    date date not null default CURRENT_DATE,
    rating int not null check (rating >= 1 and rating <= 5),
    text text,
    foreign key (book_id) references catalog.books(id) on delete cascade
);
