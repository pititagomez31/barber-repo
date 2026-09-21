# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.58barberstudio.com",
        "https://58barberstudio.com",
        "https://tu-frontend.vercel.app",       # si usas Vercel
        "https://tu-frontend.netlify.app",      # si usas Netlify
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
