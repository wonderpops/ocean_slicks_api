import sqlalchemy
import databases

engine = sqlalchemy.create_engine("")
database = databases.Database("")
metadata = sqlalchemy.MetaData()
metadata.create_all(engine)