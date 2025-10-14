"""
Main GraphQL schema for Infobús project.
"""
import strawberry
from .queries import Query


schema = strawberry.Schema(query=Query)