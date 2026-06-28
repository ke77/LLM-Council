from app import create_app

app = create_app()

if __name__ == "__main__":
     app.run(
          host="localhost",
          port=5000,
          debug=app.config["DEBUG"] # auto-reload on code changes, like Next.js's fast refresh
     )