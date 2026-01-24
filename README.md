# FrameVault

A free, AI-powered visual reference library for film frames. No signup required.

Similar to [Frameset.app](https://frameset.app/), but completely free and open for anyone to use.

![FrameVault Preview](https://images.unsplash.com/photo-1534972195531-d756b9bfa9f2?w=800&h=400&fit=crop)

## Features

- **AI-Powered Search**: Natural language search that understands mood, lighting, composition, and color
- **Auto-Tagging**: AI automatically analyzes and tags uploaded frames
- **Visual Similarity**: Find visually similar frames based on style, color, and mood
- **No Signup Required**: Free access to browse and download all content
- **Admin Panel**: Full management interface for uploading and organizing frames
- **Color Palette Extraction**: Automatic color analysis for each frame
- **Responsive Design**: Beautiful dark theme UI that works on all devices

## Quick Start

### Option 1: Static Site (No Server Required)

Simply open `index.html` in your browser or serve the folder with any static file server:

```bash
# Using Python
python -m http.server 8000

# Using Node.js
npx serve .

# Using PHP
php -S localhost:8000
```

Then open http://localhost:8000 in your browser.

### Option 2: Full Backend (For Production)

1. Install dependencies:
```bash
npm install
```

2. Start the server:
```bash
npm start
# or for development with auto-reload:
npm run dev
```

3. Open http://localhost:3001 in your browser

## Project Structure

```
framevault/
├── index.html          # Main frontend application
├── admin/
│   └── index.html      # Admin panel for uploads
├── content/            # ⭐ YOUR CONTENT GOES HERE
│   ├── frames.json     # Frame metadata (edit this!)
│   ├── your-image.jpg  # Your images
│   └── your-clip.gif   # Your GIFs
├── server.js           # Backend server (optional)
├── data/
│   └── frames.json     # Frame database (for backend)
├── assets/
│   ├── frames/         # Full-size images (for backend)
│   └── thumbnails/     # Generated thumbnails
└── README.md
```

## Adding Your Content (Easy Way)

The simplest way to add frames to your library:

### Step 1: Add your files
Drop your images and GIFs into the `content/` folder.

### Step 2: Edit frames.json
Open `content/frames.json` and add entries for each file:

```json
[
    {
        "id": "1",
        "title": "Frame Title",
        "source": "Movie Name",
        "year": 2024,
        "director": "Director Name",
        "dp": "Cinematographer Name",
        "tags": ["tag1", "tag2", "tag3"],
        "mood": "Mysterious",
        "lighting": "Natural",
        "color": ["#ff0000", "#00ff00", "#0000ff"],
        "aspect": "2.39:1",
        "file": "your-filename.jpg"
    }
]
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (can be any string) |
| `title` | Yes | Display title for the frame |
| `source` | Yes | Film/show name |
| `year` | Yes | Release year |
| `director` | No | Director name |
| `dp` | No | Cinematographer/DP name |
| `tags` | Yes | Array of searchable tags |
| `mood` | No | Mood descriptor (Mysterious, Epic, etc.) |
| `lighting` | No | Lighting type (Natural, Neon, etc.) |
| `color` | No | Array of 3-4 hex color codes |
| `aspect` | No | Aspect ratio (2.39:1, 1.85:1, etc.) |
| `file` | Yes | Filename in the content/ folder |

### GIF Support
- Files ending in `.gif` are automatically detected
- GIFs will continuously autoplay
- A "GIF" badge appears on the card

## API Endpoints

When running with the backend server:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/frames` | List all frames (supports filtering) |
| GET | `/api/frames/:id` | Get single frame details |
| POST | `/api/frames` | Upload new frame |
| PUT | `/api/frames/:id` | Update frame metadata |
| DELETE | `/api/frames/:id` | Delete frame |
| GET | `/api/frames/:id/similar` | Find similar frames |
| GET | `/api/tags` | Get all available tags |
| GET | `/api/search/ai` | AI-powered semantic search |
| POST | `/api/frames/bulk` | Bulk upload multiple frames |

### Query Parameters

**GET /api/frames**
- `q` - Search query (searches title, source, tags, description)
- `tags` - Filter by tags (comma-separated)
- `mood` - Filter by mood (comma-separated)
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20)

Example:
```
GET /api/frames?q=neon%20city&tags=cyberpunk,urban&mood=mysterious&page=1&limit=20
```

## AI Integration

The demo uses simulated AI analysis. For production, you can integrate with:

### OpenAI Vision
```javascript
// In server.js, replace analyzeImageWithAI function:
import OpenAI from 'openai';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

async function analyzeImageWithAI(imagePath) {
    const imageBuffer = await fs.readFile(imagePath);
    const base64Image = imageBuffer.toString('base64');

    const response = await openai.chat.completions.create({
        model: "gpt-4-vision-preview",
        messages: [{
            role: "user",
            content: [
                { type: "text", text: "Analyze this film frame. Provide: 1) mood tags 2) lighting type 3) composition 4) dominant colors 5) brief description" },
                { type: "image_url", image_url: { url: `data:image/jpeg;base64,${base64Image}` } }
            ]
        }]
    });

    // Parse response and return structured data
    return parseAIResponse(response.choices[0].message.content);
}
```

### Google Cloud Vision
```javascript
import vision from '@google-cloud/vision';

const client = new vision.ImageAnnotatorClient();

async function analyzeImageWithAI(imagePath) {
    const [result] = await client.annotateImage({
        image: { source: { filename: imagePath } },
        features: [
            { type: 'LABEL_DETECTION' },
            { type: 'IMAGE_PROPERTIES' },
            { type: 'SAFE_SEARCH_DETECTION' }
        ]
    });

    // Process and return structured data
    return processGoogleVisionResult(result);
}
```

## Customization

### Changing the Theme

Edit the CSS variables in `index.html`:

```css
:root {
    --primary-color: #6366f1;
    --bg-dark: #0f0f1a;
    --bg-card: rgba(255, 255, 255, 0.05);
}
```

### Adding Custom Tags

Edit the `ALL_TAGS` object in `index.html` to add your own tag categories:

```javascript
const ALL_TAGS = {
    genres: ["sci-fi", "drama", "action", ...],
    moods: ["mysterious", "epic", ...],
    lighting: ["natural", "neon", ...],
    // Add your own categories:
    cameras: ["35mm", "anamorphic", "digital"],
    directors: ["nolan", "villeneuve", "kubrick"]
};
```

## Deployment

### Vercel
```bash
vercel --prod
```

### Netlify
```bash
netlify deploy --prod
```

### Docker
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3001
CMD ["npm", "start"]
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use this for any project!

## Credits

- UI inspired by [Frameset.app](https://frameset.app/)
- Icons from [Heroicons](https://heroicons.com/)
- Fonts from [Google Fonts](https://fonts.google.com/)
