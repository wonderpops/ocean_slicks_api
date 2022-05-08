import sqlalchemy
import databases

engine = sqlalchemy.create_engine("postgresql+psycopg2://postgres:99019901Ss@localhost/ocean_slicks")
database = databases.Database("postgresql+psycopg2://postgres:99019901Ss@localhost/ocean_slicks")
metadata = sqlalchemy.MetaData()
metadata.create_all(engine)