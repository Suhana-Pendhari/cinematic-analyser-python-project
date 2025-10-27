import os
import sys
import threading
import queue
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk, ImageOps, ImageDraw
import pandas as pd
import matplotlib

# Use Agg backend for embedding in Tk
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# -----------------------------
# Theme Manager
# -----------------------------
class ThemeManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.current_theme: str = "dark"
        self.themes: Dict[str, Dict[str, str]] = {
            "dark": {
                "bg": "#121212",
                "panel": "#1E1E1E",
                "text": "#FFFFFF",
                "muted": "#B3B3B3",
                "accent": "#E50914",
                "accent_hover": "#ff1a24",
                "card": "#181818",
                "border": "#2A2A2A",
                "input": "#2A2A2A",
            },
            "light": {
                "bg": "#F5F5F5",
                "panel": "#FFFFFF",
                "text": "#111111",
                "muted": "#333333",
                "accent": "#1F51FF",
                "accent_hover": "#3b66ff",
                "card": "#FFFFFF",
                "border": "#E0E0E0",
                "input": "#FFFFFF",
            },
        }
        self._apply_styles()

    def get(self, key: str) -> str:
        return self.themes[self.current_theme][key]

    def toggle(self) -> None:
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self._apply_styles()

    def _apply_styles(self) -> None:
        palette = self.themes[self.current_theme]
        self.root.configure(bg=palette["bg"]) 
        style = ttk.Style(self.root)
        # Use built-in theme as base
        base_theme = "clam"
        try:
            style.theme_use(base_theme)
        except Exception:
            pass

        style.configure(
            "TFrame",
            background=palette["bg"],
            borderwidth=0,
        )
        style.configure(
            "Panel.TFrame",
            background=palette["panel"],
        )
        style.configure(
            "Card.TFrame",
            background=palette["card"],
            relief="flat",
        )
        style.configure(
            "TLabel",
            background=palette["bg"],
            foreground=palette["text"],
        )
        style.configure(
            "Muted.TLabel",
            background=palette["bg"],
            foreground=palette["muted"],
        )
        style.configure(
            "Title.TLabel",
            background=palette["bg"],
            foreground=palette["text"],
            font=("Segoe UI Semibold", 16),
        )
        style.configure(
            "Accent.TButton",
            background=palette["accent"],
            foreground="#FFFFFF",
            bordercolor=palette["accent"],
            focusthickness=0,
            relief="flat",
            padding=(14, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", palette["accent_hover"])],
        )
        style.configure(
            "TButton",
            background=palette["panel"],
            foreground=palette["text"],
            padding=(10, 6),
            relief="flat",
        )
        style.map(
            "TButton",
            background=[("active", palette["accent"]), ("pressed", palette["accent_hover"])],
            foreground=[("active", "#FFFFFF"), ("pressed", "#FFFFFF")],
        )
        style.configure(
            "TEntry",
            fieldbackground=palette["input"],
            foreground=palette["text"],
            bordercolor=palette["border"],
            padding=6,
        )
        style.configure(
            "Search.TEntry",
            fieldbackground=palette["panel"],
            foreground=palette["text"],
            bordercolor=palette["border"],
            padding=8,
        )
        style.configure(
            "Sidebar.TButton",
            background=palette["panel"],
            foreground=palette["text"],
            padding=(12, 10),
        )
        style.map(
            "Sidebar.TButton",
            background=[("active", palette["accent"]), ("pressed", palette["accent_hover"])],
            foreground=[("active", "#FFFFFF"), ("pressed", "#FFFFFF")],
        )
        
        # Style for active/highlighted sidebar button
        style.configure(
            "SidebarActive.TButton",
            background=palette["accent"],
            foreground="#FFFFFF",
            padding=(12, 10),
        )
        style.map(
            "SidebarActive.TButton",
            background=[("active", palette["accent_hover"]), ("pressed", palette["accent_hover"])],
            foreground=[("active", "#FFFFFF"), ("pressed", "#FFFFFF")],
        )


# -----------------------------
# Data Manager
# -----------------------------
REQUIRED_COLUMNS = [
    "Poster_Link",
    "Series_Title",
    "Released_Year",
    "Genre",
    "IMDB_Rating",
]


class DataManager:
    def __init__(self) -> None:
        self.original_df: Optional[pd.DataFrame] = None
        self.filtered_df: Optional[pd.DataFrame] = None

    def load_csv(self, path: str) -> None:
        try:
            df = pd.read_csv(path)
        except Exception as e:
            raise IOError(f"Failed to read CSV: {e}")

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(missing)}")

        # Normalize and coerce types
        df["Released_Year"] = pd.to_numeric(df["Released_Year"], errors="coerce")
        df["IMDB_Rating"] = pd.to_numeric(df["IMDB_Rating"], errors="coerce")
        df["Genre"] = df["Genre"].fillna("")
        df = df.dropna(subset=["Series_Title", "Released_Year", "IMDB_Rating"])  # essential rows

        self.original_df = df.reset_index(drop=True)
        self.filtered_df = self.original_df.copy()

    def is_loaded(self) -> bool:
        return self.original_df is not None

    def get_summary(self) -> Dict[str, str]:
        if self.filtered_df is None or self.filtered_df.empty:
            return {
                "total": "0",
                "avg_rating": "-",
                "year_range": "-",
                "top_genre": "-",
            }
        df = self.filtered_df
        total = len(df)
        avg = df["IMDB_Rating"].mean()
        yr_min, yr_max = int(df["Released_Year"].min()), int(df["Released_Year"].max())
        # compute most common genre token
        genre_series = (
            df["Genre"].dropna().astype(str).str.split(r",\s*").explode().str.strip()
        )
        top_genre = genre_series.mode().iloc[0] if not genre_series.empty else "-"
        return {
            "total": f"{total}",
            "avg_rating": f"{avg:.2f}",
            "year_range": f"{yr_min} - {yr_max}",
            "top_genre": f"{top_genre}",
        }

    def genres(self) -> List[str]:
        if self.original_df is None or self.original_df.empty:
            return []
        s = (
            self.original_df["Genre"].dropna().astype(str).str.split(r",\s*").explode().str.strip()
        )
        vals = sorted(set([g for g in s if g]))
        return vals

    def years_range(self) -> Tuple[int, int]:
        if self.original_df is None or self.original_df.empty:
            return (1900, 2025)
        return (
            int(self.original_df["Released_Year"].min()),
            int(self.original_df["Released_Year"].max()),
        )

    def apply_filters(
        self,
        title_query: str = "",
        selected_genres: Optional[List[str]] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_rating: Optional[float] = None,
    ) -> pd.DataFrame:
        if self.original_df is None:
            raise RuntimeError("No data loaded")
        df = self.original_df.copy()
        if title_query:
            q = title_query.lower()
            df = df[df["Series_Title"].astype(str).str.lower().str.contains(q)]

        if selected_genres:
            mask = df["Genre"].astype(str).apply(
                lambda txt: any(g in [t.strip() for t in str(txt).split(",")] for g in selected_genres)
            )
            df = df[mask]

        if min_year is not None:
            df = df[df["Released_Year"] >= min_year]
        if max_year is not None:
            df = df[df["Released_Year"] <= max_year]
        if min_rating is not None:
            df = df[df["IMDB_Rating"] >= min_rating]

        self.filtered_df = df.reset_index(drop=True)
        return self.filtered_df


# -----------------------------
# Async Image Loader with Cache
# -----------------------------
class ImageCacheLoader:
    def __init__(self, theme: ThemeManager) -> None:
        self.cache: Dict[str, ImageTk.PhotoImage] = {}
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.theme = theme
        # Fallbacks from local workspace
        self.fallback_paths = [
            os.path.join(self._workspace_dir(), "INF.png"),
            os.path.join(self._workspace_dir(), "404.webp"),
        ]

    def _workspace_dir(self) -> str:
        return os.path.dirname(os.path.abspath(sys.argv[0]))

    def request(self, url: str, target_label: tk.Label, width: int = 140, height: int = 210) -> None:
        if url in self.cache:
            target_label.configure(image=self.cache[url])
            target_label.image = self.cache[url]
            return
        self.queue.put((url, "GET", width, height, target_label))

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        # Try network fetch lazily without blocking the UI; if fails use fallback
        try:
            if url and url.startswith("http"):
                import requests  # local import to avoid hard dependency if unused

                resp = requests.get(url, timeout=6)
                if resp.status_code == 200:
                    from io import BytesIO

                    return Image.open(BytesIO(resp.content))
        except Exception:
            pass
        # try local path
        try:
            if url and os.path.exists(url):
                return Image.open(url)
        except Exception:
            pass
        # fallback to default local images
        for fp in self.fallback_paths:
            try:
                if os.path.exists(fp):
                    return Image.open(fp)
            except Exception:
                continue
        return None

    def _worker(self) -> None:
        while True:
            try:
                url, _method, width, height, target_label = self.queue.get(timeout=1)
                img = self._fetch_image(url)
                if img is None:
                    self.queue.task_done()
                    continue
                # Fit to target with letterbox onto themed background to avoid alpha issues
                target_size = (width, height)
                resized = ImageOps.contain(img.convert("RGB"), target_size)
                # themed background
                bg_hex = self.theme.get("card")
                bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (1, 3, 5)) if bg_hex.startswith('#') else (24, 24, 24)
                background = Image.new("RGB", target_size, bg_rgb)
                paste_pos = ((target_size[0] - resized.size[0]) // 2, (target_size[1] - resized.size[1]) // 2)
                background.paste(resized, paste_pos)
                # Optional subtle rounded mask for background rectangle
                radius = 12
                try:
                    mask = Image.new("L", target_size, 0)
                    md = ImageDraw.Draw(mask)
                    md.rounded_rectangle((0, 0, target_size[0], target_size[1]), radius=radius, fill=255)
                    background.putalpha(mask)
                except Exception:
                    pass
                photo = ImageTk.PhotoImage(background)
                self.cache[url] = photo
                # update UI in main thread
                def assign() -> None:
                    try:
                        target_label.configure(image=photo)
                        target_label.image = photo
                    except Exception:
                        pass

                target_label.after(0, assign)
            except queue.Empty:
                continue
            except Exception:
                pass
            finally:
                try:
                    self.queue.task_done()
                except Exception:
                    pass


# -----------------------------
# UI Components
# -----------------------------
class SidebarFrame(ttk.Frame):
    def __init__(self, master: tk.Widget, theme: ThemeManager, on_nav, on_toggle_callback=None) -> None:
        super().__init__(master, style="Panel.TFrame")
        self.theme = theme
        self.on_nav = on_nav
        self.on_toggle_callback = on_toggle_callback
        self.collapsed: bool = False
        self.current_page: str = "Home"  # Track current page for highlighting

        self.configure(width=200)
        self.grid_propagate(False)
        self.rowconfigure(10, weight=1)

        self.items = [
            ("Home", "🏠"),
            ("Dashboard", "🎬"),
            ("Year-wise Trends", "📈"),
            ("Genre Analysis", "📊"),
            ("Top 10 Movies", "🏆"),
            ("Export", "💾"),
            ("Clear Dataset", "🗑️"),
        ]
        self.buttons: List[ttk.Button] = []
        self._build_buttons()

        self.toggle_btn = ttk.Button(self, text="⟨⟩", command=self.toggle)
        self.toggle_btn.grid(row=99, column=0, sticky="sew", padx=8, pady=8)

    def _build_buttons(self) -> None:
        for b in self.buttons:
            b.destroy()
        self.buttons.clear()
        for idx, (name, icon) in enumerate(self.items):
            txt = f"{icon}" if self.collapsed else f"{icon}  {name}"
            
            # Choose style based on whether this is the current page
            button_style = "SidebarActive.TButton" if name == self.current_page else "Sidebar.TButton"
            
            btn = ttk.Button(
                self,
                text=txt,
                style=button_style,
                command=lambda n=name: self.on_nav(n),
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=8, pady=(8 if idx == 0 else 4))
            self.buttons.append(btn)

        self.configure(width=72 if self.collapsed else 200)

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        self._build_buttons()
        # Notify parent about sidebar toggle
        if self.on_toggle_callback:
            self.on_toggle_callback()

    def set_current_page(self, page: str) -> None:
        """Update the current page and refresh button highlighting"""
        self.current_page = page
        self._build_buttons()


class TopBar(ttk.Frame):
    def __init__(self, master: tk.Widget, theme: ThemeManager, on_toggle_theme) -> None:
        super().__init__(master, style="Panel.TFrame")
        self.theme = theme
        self.on_toggle_theme = on_toggle_theme

        self.columnconfigure(1, weight=1)

        title = ttk.Label(self, text="CineMatic Analyzer", style="Title.TLabel")
        subtitle = ttk.Label(self, text="Visualize the story behind every rating.", style="Muted.TLabel")
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(8, 0))
        subtitle.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        ttk.Label(self, text="").grid(row=0, column=1, rowspan=2, sticky="ew")

        theme_btn = ttk.Button(self, text="Toggle Theme", command=self.on_toggle_theme)
        theme_btn.grid(row=0, column=2, rowspan=2, sticky="e", padx=12)


class LandingFrame(ttk.Frame):
    def __init__(self, master: tk.Widget, theme: ThemeManager, on_upload) -> None:
        super().__init__(master)
        self.theme = theme
        self.on_upload = on_upload

        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0, background=self.theme.get("bg"))
        self.canvas.pack(fill="both", expand=True)

        self.bind("<Configure>", self._redraw)

        # Upload Button - Make it moderately bigger
        self.upload_btn = ttk.Button(self, text="📁 Upload Dataset", style="Accent.TButton", command=self.on_upload)
        # Configure button to be moderately larger
        self.upload_btn.configure(padding=(18, 12))  # Moderate padding increase
        # Set moderately larger font for the button
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"))
        self.upload_window_id: Optional[int] = None
        self.summary_frame = ttk.Frame(self, style="Card.TFrame")
        self.summary_labels: Dict[str, ttk.Label] = {}
        
        # Loading component
        self.loading_window_id: Optional[int] = None
        self.loading_angle = 0
        self.loading_animation_id = None
        
        # Add placeholder image
        self._add_placeholder_image()

    def _add_placeholder_image(self) -> None:
        """Add img1.jpg as background image for the landing page"""
        try:
            img_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "img1.jpg")
            if os.path.exists(img_path):
                img = Image.open(img_path)
                # Store original image for resizing
                self.background_img = img
            else:
                # Create a simple placeholder if img1.jpg doesn't exist
                self.background_img = Image.new("RGB", (1920, 1080), (20, 20, 20))
                draw = ImageDraw.Draw(self.background_img)
                draw.text((960, 540), "CineMatic Analyzer", fill="white", anchor="mm", font_size=48)
        except Exception:
            # Fallback placeholder
            self.background_img = Image.new("RGB", (1920, 1080), (20, 20, 20))
            draw = ImageDraw.Draw(self.background_img)
            draw.text((960, 540), "CineMatic", fill="white", anchor="mm", font_size=48)

    def _redraw(self, event=None) -> None:
        self.canvas.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        
        if w <= 1 or h <= 1:  # Avoid drawing on tiny canvas
            return
            
        # Create background image with overlay
        if hasattr(self, 'background_img'):
            # Resize image to fit canvas while maintaining aspect ratio
            img = self.background_img.copy()
            img = ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS)
            
            # Add darker overlay (Netflix-style)
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 170))  # Deeper semi-transparent black
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)
            
            # Convert to PhotoImage
            self.background_photo = ImageTk.PhotoImage(img)
            
            # Draw background image
            self.canvas.create_image(0, 0, image=self.background_photo, anchor="nw")
        else:
            # Fallback solid background
            self.canvas.create_rectangle(0, 0, w, h, fill=self.theme.get("bg"), outline="")
        
        # Add gradient overlay at bottom for better text readability
        self.canvas.create_rectangle(0, h//2, w, h, fill="", outline="", stipple="gray50")
        
        # Cinematic title with shadow effect
        font_title = ("Bahnschrift", min(48, w//20), "bold")
        title_text = "CineMatic Analyzer"
        tagline_text = "Visualize the story behind every rating."
        
        # Title shadow
        self.canvas.create_text(
            w // 2 + 3,
            h // 2 - 60 + 3,
            text=title_text,
            fill="black",
            font=font_title,
        )
        # Title main
        self.canvas.create_text(
            w // 2,
            h // 2 - 60,
            text=title_text,
            fill="white",
            font=font_title,
        )
        
        # Tagline shadow
        self.canvas.create_text(
            w // 2 + 2,
            h // 2 - 10 + 2,
            text=tagline_text,
            fill="black",
            font=("Segoe UI", min(18, w//40)),
        )
        # Tagline main
        self.canvas.create_text(
            w // 2,
            h // 2 - 10,
            text=tagline_text,
            fill="#E0E0E0",
            font=("Segoe UI", min(18, w//40)),
        )
        
        # Center upload button on canvas using window_create
        if self.upload_window_id is not None:
            try:
                self.canvas.delete(self.upload_window_id)
            except Exception:
                pass
        self.upload_window_id = self.canvas.create_window(
            w // 2,
            h // 2 + 40,
            window=self.upload_btn,
        )
        
        # Redraw loading animation if it's active
        if self.loading_animation_id:
            self._animate_loading()

    def show_summary(self, summary: Dict[str, str]) -> None:
        # place summary cards at bottom center with semi-transparent background
        for child in list(self.summary_frame.winfo_children()):
            child.destroy()

        cards = [
            ("Total Movies", summary.get("total", "-")),
            ("Average Rating", summary.get("avg_rating", "-")),
            ("Year Range", summary.get("year_range", "-")),
            ("Top Genre", summary.get("top_genre", "-")),
        ]
        for idx, (label, value) in enumerate(cards):
            card = ttk.Frame(self.summary_frame, style="Card.TFrame")
            # Add semi-transparent background to cards
            card.configure(style="Card.TFrame")
            ttk.Label(card, text=label, style="Muted.TLabel").pack(anchor="w", padx=12, pady=(12, 2))
            ttk.Label(card, text=value, font=("Segoe UI Semibold", 16)).pack(anchor="w", padx=12, pady=(0, 12))
            card.grid(row=0, column=idx, sticky="nsew", padx=8, pady=8)
        for i in range(len(cards)):
            self.summary_frame.columnconfigure(i, weight=1)
        # Position cards lower to not interfere with title
        self.summary_frame.place(relx=0.5, rely=0.85, anchor="center")
        
        # Hide loading animation after summary is displayed (with small delay to ensure rendering)
        self.after(100, self.hide_loading)

    def show_loading(self) -> None:
        """Show loading animation below upload button"""
        self.loading_angle = 0
        self._animate_loading()

    def hide_loading(self) -> None:
        """Hide loading animation and text"""
        if self.loading_animation_id:
            self.canvas.after_cancel(self.loading_animation_id)
            self.loading_animation_id = None
        if self.loading_window_id:
            self.canvas.delete(self.loading_window_id)
            self.loading_window_id = None
        
        # Clear any remaining loading elements from canvas
        self.canvas.delete("loading_text")
        self.canvas.delete("loading_spinner")

    def _animate_loading(self) -> None:
        """Animate the loading spinner"""
        # Clear previous loading elements
        self.canvas.delete("loading_text")
        self.canvas.delete("loading_spinner")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        if w <= 1 or h <= 1:
            return
            
        # Create loading spinner below upload button
        spinner_x = w // 2
        spinner_y = h // 2 + 100  # Below upload button
        
        # Draw circular loading spinner with rotating arc
        radius = 25  # Slightly larger for better visibility
        
        # Create the rotating arc (this is the main visual element)
        start_angle = self.loading_angle
        extent = 80  # Larger arc for better visibility
        
        # Draw the rotating arc with tag for easy removal
        self.canvas.create_arc(
            spinner_x - radius, spinner_y - radius,
            spinner_x + radius, spinner_y + radius,
            start=start_angle, extent=extent,
            fill=self.theme.get("accent"), outline="", width=0,
            tags="loading_spinner"
        )
        
        # Add loading text with tag for easy removal
        self.canvas.create_text(
            spinner_x, spinner_y + 50,
            text="Processing dataset...", fill="white",
            font=("Segoe UI", 14, "bold"),
            tags="loading_text"
        )
        
        # Update angle for next frame (smooth rotation)
        self.loading_angle = (self.loading_angle + 12) % 360
        
        # Schedule next frame (smooth animation)
        self.loading_animation_id = self.canvas.after(40, self._animate_loading)


class Scrollable(ttk.Frame):
    def __init__(self, master: tk.Widget, bg: str) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0, background=bg)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self, style="TFrame")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._inner_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Ensure inner frame width tracks canvas width
        def _on_canvas_configure(event) -> None:
            try:
                self.canvas.itemconfig(self._inner_window, width=self.canvas.winfo_width())
            except Exception:
                pass
        self.canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel scrolling
        def _on_mousewheel(event) -> None:
            delta = 0
            if hasattr(event, 'delta') and event.delta:
                delta = int(-1 * (event.delta / 120))
            elif event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            self.canvas.yview_scroll(delta, "units")

        # Bind only to this canvas, not all widgets
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.canvas.bind("<Button-4>", _on_mousewheel)
        self.canvas.bind("<Button-5>", _on_mousewheel)


class DashboardFrame(ttk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        theme: ThemeManager,
        data: DataManager,
        image_loader: ImageCacheLoader,
    ) -> None:
        super().__init__(master)
        self.theme = theme
        self.data = data
        self.image_loader = image_loader

        self.columnconfigure(0, weight=1)
        # Filters bar
        filters = ttk.Frame(self, style="Panel.TFrame")
        filters.grid(row=0, column=0, sticky="ew")
        for i in range(6):
            filters.columnconfigure(i, weight=1)

        ttk.Label(filters, text="Title").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(filters, textvariable=self.title_var, style="Search.TEntry")
        self.title_entry.grid(row=1, column=0, sticky="ew", padx=8)
        # Add placeholder text
        self.title_entry.insert(0, "Search by movie title...")
        self.title_entry.configure(foreground="gray")
        
        # Bind focus events to handle placeholder
        def on_title_focus_in(event):
            if self.title_entry.get() == "Search by movie title...":
                self.title_entry.delete(0, tk.END)
                self.title_entry.configure(foreground="white")
        
        def on_title_focus_out(event):
            if not self.title_entry.get():
                self.title_entry.insert(0, "Search by movie title...")
                self.title_entry.configure(foreground="gray")
        
        self.title_entry.bind("<FocusIn>", on_title_focus_in)
        self.title_entry.bind("<FocusOut>", on_title_focus_out)

        ttk.Label(filters, text="Genre").grid(row=0, column=1, sticky="w", padx=8, pady=8)
        self.genre_var = tk.StringVar()
        self.genre_combo = ttk.Combobox(filters, textvariable=self.genre_var, state="readonly", width=15)
        self.genre_combo.grid(row=1, column=1, sticky="ew", padx=8)
        # Set placeholder for genre combobox
        self.genre_combo.set("Select genre...")

        ttk.Label(filters, text="Year Range").grid(row=0, column=2, sticky="w", padx=8, pady=8)
        yr_min, yr_max = self.data.years_range()
        self.year_min = tk.IntVar(value=yr_min)
        self.year_max = tk.IntVar(value=yr_max)
        
        # Year range scales without labels
        self.scale_year_min = tk.Scale(filters, from_=yr_min, to=yr_max, orient="horizontal", command=lambda _=None: None)
        self.scale_year_min.set(yr_min)
        self.scale_year_min.grid(row=1, column=2, sticky="ew", padx=8)
        
        self.scale_year_max = tk.Scale(filters, from_=yr_min, to=yr_max, orient="horizontal", command=lambda _=None: None)
        self.scale_year_max.set(yr_max)
        self.scale_year_max.grid(row=1, column=3, sticky="ew", padx=8)

        ttk.Label(filters, text="Min Rating").grid(row=0, column=4, sticky="w", padx=8, pady=8)
        self.rating_var = tk.DoubleVar(value=0.0)
        self.scale_rating = tk.Scale(filters, from_=0.0, to=10.0, resolution=0.1, orient="horizontal")
        self.scale_rating.set(0.0)
        self.scale_rating.grid(row=1, column=4, sticky="ew", padx=8)

        apply_btn = ttk.Button(filters, text="Apply Filters", style="Accent.TButton", command=self.refresh_cards)
        apply_btn.grid(row=1, column=5, sticky="e", padx=8)

        # Cards area
        self.scroll = Scrollable(self, bg=self.theme.get("bg"))
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)

        self._populate_genres()
        self.refresh_cards()

    def _populate_genres(self) -> None:
        genres = ["All"] + self.data.genres()
        self.genre_combo['values'] = genres
        # Keep the placeholder text instead of setting to "All"
        self.genre_combo.set("Select genre...")

    def refresh_cards(self) -> None:
        # Validate year range
        yr_min = int(self.scale_year_min.get())
        yr_max = int(self.scale_year_max.get())
        if yr_min > yr_max:
            messagebox.showerror("Invalid Year Range", "Please select a valid year range. End year must be greater than or equal to start year.")
            return
            
        selected_genre = self.genre_var.get()
        selected = [selected_genre] if selected_genre and selected_genre != "All" and selected_genre != "Select genre..." else None
        min_rating = float(self.scale_rating.get())
        title_q = self.title_var.get().strip()
        # Handle placeholder text
        if title_q == "Search by movie title...":
            title_q = ""
        
        try:
            df = self.data.apply_filters(title_q, selected, yr_min, yr_max, min_rating)
        except Exception as e:
            messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
            return

        for child in list(self.scroll.inner.winfo_children()):
            child.destroy()

        # Check if no movies found
        if df.empty:
            no_movies_frame = ttk.Frame(self.scroll.inner, style="TFrame")
            no_movies_frame.pack(expand=True, fill="both")
            ttk.Label(no_movies_frame, text="No movies found with the specified filters", 
                     font=("Segoe UI", 16), style="Muted.TLabel").pack(expand=True)
            ttk.Label(no_movies_frame, text="Try adjusting your search criteria", 
                     font=("Segoe UI", 12), style="Muted.TLabel").pack()
            return

        # grid responsive: 5 columns on wide, adjust by width
        cols = 5
        for i in range(cols):
            self.scroll.inner.columnconfigure(i, weight=1)

        for idx, row in df.iterrows():
            r = idx // cols
            c = idx % cols
            card = ttk.Frame(self.scroll.inner, style="Card.TFrame", padding=12)
            card.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
            
            # Add hover effect
            def on_enter(event, card=card):
                card.configure(style="Card.TFrame")
            def on_leave(event, card=card):
                card.configure(style="Card.TFrame")
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)

            # Image container with border
            img_container = ttk.Frame(card, style="Card.TFrame")
            img_container.pack(fill="x", pady=(0, 8))
            
            img_label = ttk.Label(img_container)
            img_label.configure(background=self.theme.get("card"))
            img_label.pack(anchor="center")
            url = str(row.get("Poster_Link", ""))
            self.image_loader.request(url, img_label, width=140, height=210)

            # Movie info
            info_frame = ttk.Frame(card, style="TFrame")
            info_frame.pack(fill="x", expand=True)
            
            title = str(row.get("Series_Title", ""))
            year = int(row.get("Released_Year", 0)) if pd.notna(row.get("Released_Year")) else 0
            rating = float(row.get("IMDB_Rating", 0)) if pd.notna(row.get("IMDB_Rating")) else 0
            genre = str(row.get("Genre", ""))
            
            # Title with better styling
            title_label = ttk.Label(info_frame, text=title, font=("Segoe UI Semibold", 12))
            title_label.pack(anchor="w", pady=(0, 4))
            title_label.configure(wraplength=160)
            
            # Year and rating
            ttk.Label(info_frame, text=f"{year} • ⭐ {rating:.1f}", style="Muted.TLabel", 
                     font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 4))
            
            # Genre with better formatting
            genre_text = genre[:50] + "..." if len(genre) > 50 else genre
            ttk.Label(info_frame, text=genre_text, style="Muted.TLabel", 
                     font=("Segoe UI", 9), wraplength=160, justify="left").pack(anchor="w", pady=(0, 8))

            # View Details button
            def open_details(idx=idx) -> None:
                DetailsModal(self.winfo_toplevel(), self.theme, self.data, idx, self.image_loader)

            details_btn = ttk.Button(info_frame, text="View Details", style="Accent.TButton", command=open_details)
            details_btn.pack(anchor="e", pady=(4, 0))


class DetailsModal(tk.Toplevel):
    def __init__(self, master: tk.Widget, theme: ThemeManager, data: DataManager, index: int, image_loader=None) -> None:
        super().__init__(master)
        self.theme = theme
        self.data = data
        self.image_loader = image_loader
        self.configure(bg=self.theme.get("panel"))
        self.title("Movie Details")
        self.geometry("800x600")
        self.transient(master)
        self.grab_set()

        container = ttk.Frame(self, padding=16, style="TFrame")
        container.pack(fill="both", expand=True)

        if self.data.filtered_df is None or index >= len(self.data.filtered_df):
            ttk.Label(container, text="No data available").pack()
            return
        row = self.data.filtered_df.iloc[index]

        title = str(row.get("Series_Title", ""))
        details = [
            ("Year", str(row.get("Released_Year", ""))),
            ("Rating", str(row.get("IMDB_Rating", ""))),
            ("Genre", str(row.get("Genre", ""))),
        ]
        # Optional fields if exist in dataset
        for opt in ["Overview", "Director", "Star1", "Star2", "Star3", "Star4", "Meta_score"]:
            if opt in row.index and pd.notna(row[opt]):
                details.append((opt.replace("_", " "), str(row[opt])))

        # Main content frame with image and details
        main_frame = ttk.Frame(container, style="TFrame")
        main_frame.pack(fill="both", expand=True)

        # Image frame on the left
        image_frame = ttk.Frame(main_frame, style="Card.TFrame")
        image_frame.pack(side="left", fill="y", padx=(0, 16))
        
        # Movie poster
        poster_label = ttk.Label(image_frame)
        poster_label.pack(padx=16, pady=16)
        
        # Load poster image
        if self.image_loader:
            poster_url = str(row.get("Poster_Link", ""))
            self.image_loader.request(poster_url, poster_label, width=200, height=300)
        else:
            # Fallback placeholder
            placeholder = Image.new("RGB", (200, 300), (50, 50, 50))
            draw = ImageDraw.Draw(placeholder)
            draw.text((100, 150), "No Image", fill="white", anchor="mm")
            photo = ImageTk.PhotoImage(placeholder)
            poster_label.configure(image=photo)
            poster_label.image = photo

        # Details frame on the right
        details_frame = ttk.Frame(main_frame, style="TFrame")
        details_frame.pack(side="right", fill="both", expand=True)

        ttk.Label(details_frame, text=title, font=("Segoe UI Semibold", 20)).pack(anchor="w", pady=(0, 16))
        
        body = Scrollable(details_frame, bg=self.theme.get("panel"))
        body.pack(fill="both", expand=True)

        for k, v in details:
            frame = ttk.Frame(body.inner, style="Card.TFrame")
            ttk.Label(frame, text=k, style="Muted.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
            ttk.Label(frame, text=v, wraplength=500, justify="left").pack(anchor="w", padx=12, pady=(0, 12))
            frame.pack(fill="x", pady=8)

        ttk.Button(container, text="Close", command=self.destroy).pack(anchor="e", pady=8)


class TrendsFrame(ttk.Frame):
    def __init__(self, master: tk.Widget, theme: ThemeManager, data: DataManager) -> None:
        super().__init__(master)
        self.theme = theme
        self.data = data
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Title for the page
        ttk.Label(self, text="Year-wise Trends - Average Ratings Over Time", 
                 font=("Segoe UI Semibold", 16)).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.canvas = None
        self.draw_chart()

    def draw_chart(self) -> None:
        # Clear existing chart widget if any
        for child in list(self.grid_slaves(row=1, column=0)):
            child.destroy()
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to view year-wise trends.")
            ttk.Label(self, text="Please upload a dataset first").grid(row=1, column=0, padx=16, pady=16)
            return
        if self.data.filtered_df is None or self.data.filtered_df.empty:
            ttk.Label(self, text="No data available").grid(row=1, column=0, padx=16, pady=16)
            return
        df = self.data.filtered_df
        trend = df.groupby("Released_Year")["IMDB_Rating"].mean().reset_index()
        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(trend["Released_Year"], trend["IMDB_Rating"], color=self.theme.get("accent"), linewidth=2, marker='o', markersize=4)
        ax.set_title("Average Ratings Over Time", fontsize=14, fontweight='bold')
        ax.set_xlabel("Year", fontsize=12)
        ax.set_ylabel("Average Rating", fontsize=12)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.canvas = canvas


class GenreAnalysisFrame(ttk.Frame):
    def __init__(self, master: tk.Widget, theme: ThemeManager, data: DataManager) -> None:
        super().__init__(master)
        self.theme = theme
        self.data = data
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Title for the page
        ttk.Label(self, text="Genre Analysis - Average Ratings by Genre", 
                 font=("Segoe UI Semibold", 16)).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.canvas = None
        self.draw_chart()

    def draw_chart(self) -> None:
        # Clear existing chart widget if any
        for child in list(self.grid_slaves(row=1, column=0)):
            child.destroy()
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to view genre analysis.")
            ttk.Label(self, text="Please upload a dataset first").grid(row=1, column=0, padx=16, pady=16)
            return
        if self.data.filtered_df is None or self.data.filtered_df.empty:
            ttk.Label(self, text="No data available").grid(row=1, column=0, padx=16, pady=16)
            return
        df = self.data.filtered_df
        # explode genres to compute averages per genre
        exploded = df.assign(GenreToken=df["Genre"].astype(str).str.split(r",\s*")).explode("GenreToken")
        exploded["GenreToken"] = exploded["GenreToken"].str.strip()
        grp = exploded.groupby("GenreToken")["IMDB_Rating"].mean().dropna().sort_values(ascending=False).head(15)
        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        bars = ax.bar(grp.index, grp.values, color=self.theme.get("accent"))
        ax.set_title("Average Rating by Genre", fontsize=14, fontweight='bold')
        ax.set_xlabel("Genre", fontsize=12)
        ax.set_ylabel("Average Rating", fontsize=12)
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, axis='y', alpha=0.3)
        
        # Add value labels on top of bars
        for bar, value in zip(bars, grp.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, 
                   f'{value:.2f}', ha='center', va='bottom', fontsize=9)
        
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.canvas = canvas


class Top10Frame(ttk.Frame):
    def __init__(self, master: tk.Widget, theme: ThemeManager, data: DataManager, image_loader=None) -> None:
        super().__init__(master)
        self.theme = theme
        self.data = data
        self.image_loader = image_loader
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)  # Give more space to chart
        self.rowconfigure(1, weight=1)

        # Title for the page
        ttk.Label(self, text="Top 10 Movies by Rating", 
                 font=("Segoe UI Semibold", 16)).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))

        self.draw()

    def draw(self) -> None:
        # Clear existing content except title
        for child in list(self.grid_slaves(row=1, column=0)) + list(self.grid_slaves(row=1, column=1)):
            child.destroy()
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to view top 10 movies.")
            ttk.Label(self, text="Please upload a dataset first").grid(row=1, column=0, columnspan=2, padx=16, pady=16)
            self.canvas = None
            return
        if self.data.filtered_df is None or self.data.filtered_df.empty:
            ttk.Label(self, text="No data available").grid(row=1, column=0, columnspan=2, padx=16, pady=16)
            self.canvas = None
            return
        df = self.data.filtered_df.sort_values("IMDB_Rating", ascending=False).head(10)
        # table with scrollbar on left
        table_frame = ttk.Frame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=8)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        cols = ("Title", "Year", "Rating")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="w", width=220 if c == "Title" else 80)
        for idx, (_, r) in enumerate(df.iterrows()):
            tree.insert("", "end", values=(str(r.get("Series_Title", "")), int(r.get("Released_Year", 0)), float(r.get("IMDB_Rating", 0))))
        
        # Make table rows clickable
        def on_row_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                values = item['values']
                # Find the corresponding row in dataframe
                for idx, (_, r) in enumerate(df.iterrows()):
                    if (str(r.get("Series_Title", "")) == values[0] and 
                        int(r.get("Released_Year", 0)) == values[1] and 
                        float(r.get("IMDB_Rating", 0)) == values[2]):
                        DetailsModal(self.winfo_toplevel(), self.theme, self.data, idx, self.image_loader)
                        break
        
        tree.bind("<Double-1>", on_row_click)  # Double-click to open details
        
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        # chart
        chart_frame = ttk.Frame(self)
        chart_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=8)
        chart_frame.rowconfigure(0, weight=1)
        chart_frame.columnconfigure(0, weight=1)
        
        fig = Figure(figsize=(8, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        # Truncate long titles for better display
        titles = [title[:30] + "..." if len(title) > 30 else title for title in list(df["Series_Title"])[::-1]]
        ratings = list(df["IMDB_Rating"])[::-1]
        
        bars = ax.barh(range(len(titles)), ratings, color=self.theme.get("accent"))
        ax.set_yticks(range(len(titles)))
        ax.set_yticklabels(titles, fontsize=9)
        ax.set_xlabel("Rating", fontsize=10)
        ax.set_title("Top 10 Movies by Rating", fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for i, (bar, rating) in enumerate(zip(bars, ratings)):
            ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2, 
                   f'{rating:.1f}', va='center', fontsize=8)
        
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.grid(row=0, column=0, sticky="nsew")
        self.canvas = canvas


# -----------------------------
# Main Application
# -----------------------------
class CineMaticApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CineMatic Analyzer")
        self.geometry("1200x800")
        self.minsize(1024, 700)

        self.theme = ThemeManager(self)
        self.data = DataManager()
        self.image_loader = ImageCacheLoader(self.theme)

        # Layout: sidebar | main area with top bar + content
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self.sidebar = SidebarFrame(self, self.theme, self.navigate, self._on_sidebar_toggle)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")

        self.topbar = TopBar(self, self.theme, self._toggle_theme)
        self.topbar.grid(row=0, column=1, sticky="ew")

        self.content = ttk.Frame(self, style="TFrame")
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        # Pages
        self.pages: Dict[str, ttk.Frame] = {}
        self.landing = LandingFrame(self.content, self.theme, self._upload_dataset)
        self.landing.grid(row=0, column=0, sticky="nsew")
        self.pages["Home"] = self.landing


    def _toggle_theme(self) -> None:
        self.theme.toggle()
        # Re-render current page when toggling theme
        self.navigate(self._current_page_name())

    def _on_sidebar_toggle(self) -> None:
        """Handle sidebar toggle - redraw export content if on export page"""
        current_page = self._current_page_name()
        if current_page == "Export":
            # Find the export frame and trigger a redraw
            export_frame = self.pages.get("Export")
            if export_frame and hasattr(export_frame, 'export_canvas'):
                # Use the stored canvas reference to trigger redraw
                self._redraw_export_content(export_frame.export_canvas)

    def _current_page_name(self) -> str:
        for name, frame in self.pages.items():
            if frame.winfo_ismapped():
                return name
        return "Home"

    def _upload_dataset(self) -> None:
        path = filedialog.askopenfilename(
            title="Select CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not path:
            return
        
        # Show loading animation
        self.landing.show_loading()
        
        # Process dataset in a separate thread to avoid blocking UI
        import threading
        def process_dataset():
            try:
                self.data.load_csv(path)
                # Schedule UI updates on main thread
                self.after(0, self._on_dataset_loaded_success)
            except Exception as e:
                # Schedule error handling on main thread
                self.after(0, lambda: self._on_dataset_loaded_error(str(e)))
        
        # Start processing in background thread
        thread = threading.Thread(target=process_dataset, daemon=True)
        thread.start()

    def _on_dataset_loaded_success(self) -> None:
        """Handle successful dataset loading"""
        # Show success message first
        messagebox.showinfo("Success", "Dataset uploaded successfully!")
        # Update UI (this will show summary and hide loading)
        self._on_dataset_loaded()

    def _on_dataset_loaded_error(self, error_msg: str) -> None:
        """Handle dataset loading error"""
        # Hide loading animation
        self.landing.hide_loading()
        # Show error message
        messagebox.showerror("Error", error_msg)

    def _clear_dataset(self) -> None:
        """Clear the uploaded dataset and reset the application"""
        if not self.data.is_loaded():
            messagebox.showinfo("No Dataset", "No dataset is currently loaded.")
            return
            
        # Show confirmation dialog
        result = messagebox.askyesno(
            "Clear Dataset", 
            "Are you sure you want to clear the current dataset?\n\nThis will remove all data and disable analysis features until a new dataset is uploaded.",
            icon="warning"
        )
        
        if result:
            # Clear the dataset
            self.data.original_df = None
            self.data.filtered_df = None
            
            # Clear the landing page summary
            self.landing.summary_frame.place_forget()
            
            # Destroy and rebuild all analysis pages to reset them
            self._reset_analysis_pages()
            
            # Navigate to home page
            self.navigate("Home")
            
            # Show confirmation message
            messagebox.showinfo("Dataset Cleared", "Dataset has been successfully removed.\n\nAll analysis features are now disabled until you upload a new dataset.")

    def _reset_analysis_pages(self) -> None:
        """Reset all analysis pages to their initial state"""
        # Remove all analysis pages from the pages dictionary
        analysis_pages = ["Dashboard", "Year-wise Trends", "Genre Analysis", "Top 10 Movies", "Export"]
        for page_name in analysis_pages:
            if page_name in self.pages:
                self.pages[page_name].destroy()
                del self.pages[page_name]

    def _on_dataset_loaded(self) -> None:
        # Update landing summary (this will hide loading and show summary cards)
        self.landing.show_summary(self.data.get_summary())
        # Build other pages when data exists
        self._build_or_refresh_pages()

    def _build_or_refresh_pages(self) -> None:
        # Dashboard
        dash = self.pages.get("Dashboard")
        if dash is not None:
            dash.destroy()
        dash = DashboardFrame(self.content, self.theme, self.data, self.image_loader)
        dash.grid(row=0, column=0, sticky="nsew")
        self.pages["Dashboard"] = dash

        # Trends
        trends = self.pages.get("Year-wise Trends")
        if trends is not None:
            trends.destroy()
        trends = TrendsFrame(self.content, self.theme, self.data)
        trends.grid(row=0, column=0, sticky="nsew")
        self.pages["Year-wise Trends"] = trends

        # Genre Analysis
        ga = self.pages.get("Genre Analysis")
        if ga is not None:
            ga.destroy()
        ga = GenreAnalysisFrame(self.content, self.theme, self.data)
        ga.grid(row=0, column=0, sticky="nsew")
        self.pages["Genre Analysis"] = ga

        # Top 10
        t10 = self.pages.get("Top 10 Movies")
        if t10 is not None:
            t10.destroy()
        t10 = Top10Frame(self.content, self.theme, self.data, self.image_loader)
        t10.grid(row=0, column=0, sticky="nsew")
        self.pages["Top 10 Movies"] = t10

        # Export placeholder frame uses current filtered data
        exp = self.pages.get("Export")
        if exp is not None:
            exp.destroy()
        exp = self._build_export_frame()
        exp.grid(row=0, column=0, sticky="nsew")
        self.pages["Export"] = exp

        # Return to home to show summary
        self.navigate("Home")

    def _build_export_frame(self) -> ttk.Frame:
        frame = ttk.Frame(self.content)
        
        # Create canvas for full background image
        canvas = tk.Canvas(frame, bd=0, highlightthickness=0, background=self.theme.get("bg"))
        canvas.pack(fill="both", expand=True)
        
        # Store canvas reference for sidebar toggle redraw
        frame.export_canvas = canvas
        
        # Bind canvas resize event
        frame.bind("<Configure>", lambda e: self._redraw_export_content(canvas))
        
        # Bind click events for button handling
        canvas.bind("<Button-1>", lambda e: self._handle_export_click(canvas, e.x, e.y))
        
        # Add background image and content
        self._add_export_background_image(canvas)

        return frame

    def _add_export_background_image(self, canvas) -> None:
        """Add img2.jpg as background image for the export page"""
        try:
            img_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "img2.jpg")
            if os.path.exists(img_path):
                img = Image.open(img_path)
                # Store original image for resizing
                self.export_background_img = img
            else:
                # Create a simple placeholder if img2.jpg doesn't exist
                self.export_background_img = Image.new("RGB", (1920, 1080), (20, 20, 20))
                draw = ImageDraw.Draw(self.export_background_img)
                draw.text((960, 540), "Export Center", fill="white", anchor="mm", font_size=48)
        except Exception:
            # Fallback placeholder
            self.export_background_img = Image.new("RGB", (1920, 1080), (20, 20, 20))
            draw = ImageDraw.Draw(self.export_background_img)
            draw.text((960, 540), "Export", fill="white", anchor="mm", font_size=48)

        # Initial draw
        self._redraw_export_content(canvas)

    def _redraw_export_content(self, canvas) -> None:
        """Redraw the export page content on canvas"""
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        
        if w <= 1 or h <= 1:  # Avoid drawing on tiny canvas
            return
            
        # Create background image with overlay
        if hasattr(self, 'export_background_img'):
            # Resize image to fit canvas while maintaining aspect ratio
            img = self.export_background_img.copy()
            img = ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS)
            
            # Add darker overlay (Netflix-style)
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 170))  # Deeper semi-transparent black
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)
            
            # Convert to PhotoImage
            self.export_background_photo = ImageTk.PhotoImage(img)
            
            # Draw background image
            canvas.create_image(0, 0, image=self.export_background_photo, anchor="nw")
        else:
            # Fallback solid background
            canvas.create_rectangle(0, 0, w, h, fill=self.theme.get("bg"), outline="")
        
        # Add gradient overlay at bottom for better text readability
        canvas.create_rectangle(0, h//2, w, h, fill="", outline="", stipple="gray50")
        
        # No center content - just background image
        
        # Add all previous export content on the left side
        self._create_export_content_overlay(canvas, w, h)

    def _create_export_content_overlay(self, canvas, w, h) -> None:
        """Create all previous export content as overlay on the left side"""
        # Create larger content area (up to 70% of width)
        content_width = min(700, int(w * 0.7))
        content_x = 30
        content_y = 30
        content_height = h - 60
        
        # Semi-transparent background for content
        canvas.create_rectangle(
            content_x, content_y, content_x + content_width, content_y + content_height,
            fill="black", outline="", stipple="gray25"
        )
        
        # Title
        canvas.create_text(
            content_x + 20, content_y + 30,
            text="📤 Export Options", fill="white", font=("Segoe UI Semibold", 20),
            anchor="w"
        )
        
        # Data Export Section
        data_y = content_y + 70
        canvas.create_text(
            content_x + 20, data_y,
            text="📊 Data Export", fill="#E50914", font=("Segoe UI Semibold", 14),
            anchor="w"
        )
        
        # Data export buttons
        btn_y = data_y + 30
        btn_width = 280
        btn_height = 40
        
        # CSV Export button
        csv_btn = canvas.create_rectangle(
            content_x + 20, btn_y, content_x + 20 + btn_width, btn_y + btn_height,
            fill="#E50914", outline="", width=0
        )
        canvas.create_text(
            content_x + 20 + btn_width // 2, btn_y + btn_height // 2,
            text="📄 Export All Filtered Data (CSV)", fill="white", font=("Segoe UI", 10, "bold")
        )
        
        # Top 10 CSV button
        top10_btn = canvas.create_rectangle(
            content_x + 20, btn_y + btn_height + 10, content_x + 20 + btn_width, btn_y + btn_height + 10 + btn_height,
            fill="#E50914", outline="", width=0
        )
        canvas.create_text(
            content_x + 20 + btn_width // 2, btn_y + btn_height + 10 + btn_height // 2,
            text="🏆 Export Top 10 Movies (CSV)", fill="white", font=("Segoe UI", 10, "bold")
        )
        
        # Individual Chart Export Section
        chart_y = btn_y + btn_height * 2 + 50
        canvas.create_text(
            content_x + 20, chart_y,
            text="📈 Individual Chart Export", fill="#1F51FF", font=("Segoe UI Semibold", 14),
            anchor="w"
        )
        
        # Chart table headers
        table_y = chart_y + 30
        canvas.create_text(
            content_x + 20, table_y,
            text="Chart Name", fill="white", font=("Segoe UI Semibold", 12),
            anchor="w"
        )
        canvas.create_text(
            content_x + 250, table_y,
            text="Export as Image", fill="white", font=("Segoe UI Semibold", 12),
            anchor="w"
        )
        canvas.create_text(
            content_x + 450, table_y,
            text="Export as PDF", fill="white", font=("Segoe UI Semibold", 12),
            anchor="w"
        )
        
        # Chart rows
        charts = [
            ("📊 Year-wise Trends Chart", "Year-wise Trends"),
            ("📈 Genre Analysis Chart", "Genre Analysis"),
            ("🏆 Top 10 Movies Chart", "Top 10 Movies")
        ]
        
        for i, (chart_name, chart_key) in enumerate(charts):
            row_y = table_y + 30 + (i * 40)
            
            # Chart name
            canvas.create_text(
                content_x + 20, row_y,
                text=chart_name, fill="white", font=("Segoe UI", 10),
                anchor="w"
            )
            
            # PNG button
            png_btn = canvas.create_rectangle(
                content_x + 250, row_y - 18, content_x + 350, row_y + 18,
                fill="#1F51FF", outline="", width=0
            )
            canvas.create_text(
                content_x + 300, row_y,
                text="🖼️ PNG", fill="white", font=("Segoe UI", 11, "bold")
            )
            
            # PDF button
            pdf_btn = canvas.create_rectangle(
                content_x + 450, row_y - 18, content_x + 550, row_y + 18,
                fill="#1F51FF", outline="", width=0
            )
            canvas.create_text(
                content_x + 500, row_y,
                text="📄 PDF", fill="white", font=("Segoe UI", 11, "bold")
            )
        
        # Bulk Export Section
        bulk_y = chart_y + 200
        canvas.create_text(
            content_x + 20, bulk_y,
            text="📚 Bulk Export Options", fill="#FF6B35", font=("Segoe UI Semibold", 14),
            anchor="w"
        )
        
        # Bulk export buttons
        bulk_btn_y = bulk_y + 30
        bulk_btn_width = 320
        bulk_btn_height = 40
        
        # All PDF button
        all_pdf_btn = canvas.create_rectangle(
            content_x + 20, bulk_btn_y, content_x + 20 + bulk_btn_width, bulk_btn_y + bulk_btn_height,
            fill="#FF6B35", outline="", width=0
        )
        canvas.create_text(
            content_x + 20 + bulk_btn_width // 2, bulk_btn_y + bulk_btn_height // 2,
            text="📄 Export All Charts as PDF", fill="white", font=("Segoe UI", 10, "bold")
        )
        
        # Summary PDF button
        summary_btn = canvas.create_rectangle(
            content_x + 20, bulk_btn_y + bulk_btn_height + 10, content_x + 20 + bulk_btn_width, bulk_btn_y + bulk_btn_height + 10 + bulk_btn_height,
            fill="#FF6B35", outline="", width=0
        )
        canvas.create_text(
            content_x + 20 + bulk_btn_width // 2, bulk_btn_y + bulk_btn_height + 10 + bulk_btn_height // 2,
            text="📊 Export Summary Report (PDF)", fill="white", font=("Segoe UI", 10, "bold")
        )
        
        # Store all button positions for click handling
        self.export_content_buttons = {
            'csv': (content_x + 20, btn_y, content_x + 20 + btn_width, btn_y + btn_height),
            'top10': (content_x + 20, btn_y + btn_height + 10, content_x + 20 + btn_width, btn_y + btn_height + 10 + btn_height),
            'trends_png': (content_x + 250, table_y + 30 - 18, content_x + 350, table_y + 30 + 18),
            'trends_pdf': (content_x + 450, table_y + 30 - 18, content_x + 550, table_y + 30 + 18),
            'genre_png': (content_x + 250, table_y + 70 - 18, content_x + 350, table_y + 70 + 18),
            'genre_pdf': (content_x + 450, table_y + 70 - 18, content_x + 550, table_y + 70 + 18),
            'top10_png': (content_x + 250, table_y + 110 - 18, content_x + 350, table_y + 110 + 18),
            'top10_pdf': (content_x + 450, table_y + 110 - 18, content_x + 550, table_y + 110 + 18),
            'all_pdf': (content_x + 20, bulk_btn_y, content_x + 20 + bulk_btn_width, bulk_btn_y + bulk_btn_height),
            'summary': (content_x + 20, bulk_btn_y + bulk_btn_height + 10, content_x + 20 + bulk_btn_width, bulk_btn_y + bulk_btn_height + 10 + bulk_btn_height)
        }

    def _handle_export_click(self, canvas, x, y) -> None:
        """Handle clicks on export buttons"""
        # Check left side content buttons
        if hasattr(self, 'export_content_buttons'):
            for button_name, (x1, y1, x2, y2) in self.export_content_buttons.items():
                if x1 <= x <= x2 and y1 <= y <= y2:
                    if button_name == 'csv':
                        self._export_csv()
                    elif button_name == 'top10':
                        self._export_top10_table()
                    elif button_name == 'trends_png':
                        self._export_single_chart("Year-wise Trends", "png")
                    elif button_name == 'trends_pdf':
                        self._export_single_chart("Year-wise Trends", "pdf")
                    elif button_name == 'genre_png':
                        self._export_single_chart("Genre Analysis", "png")
                    elif button_name == 'genre_pdf':
                        self._export_single_chart("Genre Analysis", "pdf")
                    elif button_name == 'top10_png':
                        self._export_single_chart("Top 10 Movies", "png")
                    elif button_name == 'top10_pdf':
                        self._export_single_chart("Top 10 Movies", "pdf")
                    elif button_name == 'all_pdf':
                        self._export_all_charts_pdf()
                    elif button_name == 'summary':
                        self._export_summary_pdf()
                    return

    def _export_csv(self) -> None:
        """Export filtered data as CSV"""
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to export data.")
            return
        if self.data.filtered_df is None or self.data.filtered_df.empty:
            messagebox.showwarning("Export", "No filtered data to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            self.data.filtered_df.to_csv(path, index=False)
            messagebox.showinfo("Export", "CSV exported successfully.")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export CSV: {e}")

    def _export_top10_table(self) -> None:
        """Export top 10 movies as CSV"""
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to export top 10 movies.")
            return
        if self.data.filtered_df is None or self.data.filtered_df.empty:
            messagebox.showwarning("Export", "No filtered data to export.")
            return
        
        # Get top 10 movies
        top10_df = self.data.filtered_df.sort_values("IMDB_Rating", ascending=False).head(10)
        
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            # Export with selected columns
            export_df = top10_df[["Series_Title", "Released_Year", "IMDB_Rating", "Genre"]].copy()
            export_df.to_csv(path, index=False)
            messagebox.showinfo("Export", "Top 10 movies exported successfully.")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export top 10 movies: {e}")

    def _export_single_chart(self, chart_name, format_type):
        """Export a single chart"""
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to export charts.")
            return
        
        page = self.pages.get(chart_name)
        if not page or not hasattr(page, "canvas") or not page.canvas:
            messagebox.showwarning("Export", f"{chart_name} chart is not available.")
            return
        
        # Get file extension and filter
        if format_type == "pdf":
            filetypes = [("PDF", "*.pdf")]
            defaultextension = ".pdf"
        else:
            filetypes = [("PNG", "*.png")]
            defaultextension = ".png"
        
        path = filedialog.asksaveasfilename(defaultextension=defaultextension, filetypes=filetypes)
        if not path:
            return
        
        try:
            fig = page.canvas.figure
            if format_type == "pdf":
                from matplotlib.backends.backend_pdf import PdfPages
                with PdfPages(path) as pdf:
                    pdf.savefig(fig, bbox_inches="tight")
                messagebox.showinfo("Export", f"{chart_name} exported as PDF successfully.")
            else:
                fig.savefig(path, dpi=200, bbox_inches="tight")
                messagebox.showinfo("Export", f"{chart_name} exported as PNG successfully.")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export {chart_name}: {e}")

    def _export_all_charts_pdf(self):
        """Export all charts as PDF"""
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to export charts.")
            return
        
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        
        try:
            from matplotlib.backends.backend_pdf import PdfPages
            import matplotlib.pyplot as plt
            
            with PdfPages(path) as pdf:
                # Add all three charts
                for chart_name in ["Year-wise Trends", "Genre Analysis", "Top 10 Movies"]:
                    page = self.pages.get(chart_name)
                    if page and hasattr(page, "canvas") and page.canvas:
                        fig = page.canvas.figure
                        pdf.savefig(fig, bbox_inches="tight")
                        plt.close(fig)
            
            messagebox.showinfo("Export", "All charts exported to PDF successfully.")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export all charts: {e}")

    def _export_summary_pdf(self):
        """Export summary report with all charts as PDF"""
        if not self.data.is_loaded():
            messagebox.showwarning("No Dataset", "Please upload a dataset first to export summary.")
            return
        
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        
        try:
            from matplotlib.backends.backend_pdf import PdfPages
            from matplotlib.figure import Figure
            import matplotlib.pyplot as plt
            
            with PdfPages(path) as pdf:
                # Page 1: Dataset Summary
                summary_fig = Figure(figsize=(8.5, 11))
                summary_ax = summary_fig.add_subplot(111)
                summary_ax.axis('off')
                
                # Get summary data
                summary = self.data.get_summary()
                
                # Create summary text
                summary_text = f"""
CineMatic Analyzer - Dataset Summary Report

Dataset Overview:
• Total Movies: {summary['total']}
• Average Rating: {summary['avg_rating']}
• Year Range: {summary['year_range']}
• Top Genre: {summary['top_genre']}

Analysis Charts:
• Year-wise Trends: Shows average ratings over time
• Genre Analysis: Displays average ratings by genre
• Top 10 Movies: Highest rated movies in the dataset

Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                summary_ax.text(0.1, 0.9, summary_text, transform=summary_ax.transAxes, 
                               fontsize=12, verticalalignment='top', fontfamily='monospace')
                
                pdf.savefig(summary_fig, bbox_inches="tight")
                plt.close(summary_fig)
                
                # Add all three charts
                for chart_name in ["Year-wise Trends", "Genre Analysis", "Top 10 Movies"]:
                    page = self.pages.get(chart_name)
                    if page and hasattr(page, "canvas") and page.canvas:
                        fig = page.canvas.figure
                        pdf.savefig(fig, bbox_inches="tight")
                        plt.close(fig)
            
            messagebox.showinfo("Export", "Summary report with all charts exported to PDF successfully.")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export summary: {e}")

    def navigate(self, page: str) -> None:
        # Handle Clear Dataset option
        if page == "Clear Dataset":
            self._clear_dataset()
            return
            
        # Check if trying to access analysis pages without dataset
        analysis_pages = ["Dashboard", "Year-wise Trends", "Genre Analysis", "Top 10 Movies", "Export"]
        if page in analysis_pages and not self.data.is_loaded():
            messagebox.showwarning("No Dataset", f"Please upload a dataset first to access {page}.")
            return
            
        # hide all
        for f in self.pages.values():
            f.grid_remove()
        # show target
        if page not in self.pages:
            page = "Home"
        self.pages[page].grid()
        
        # Update sidebar highlighting
        self.sidebar.set_current_page(page)


def main() -> None:
    app = CineMaticApp()
    app.mainloop()


if __name__ == "__main__":
    main()
