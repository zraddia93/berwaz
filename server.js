/**
 * FrameVault Backend Server
 *
 * This is a Node.js/Express backend for FrameVault.
 * It handles frame uploads, AI analysis, and API endpoints.
 *
 * To use:
 * 1. Run: npm install express cors multer sharp uuid
 * 2. Run: node server.js
 * 3. Server starts at http://localhost:3001
 *
 * For production AI integration, add your preferred API:
 * - OpenAI Vision: Set OPENAI_API_KEY environment variable
 * - Google Cloud Vision: Set GOOGLE_APPLICATION_CREDENTIALS
 * - Anthropic Claude: Set ANTHROPIC_API_KEY
 */

import express from 'express';
import cors from 'cors';
import multer from 'multer';
import sharp from 'sharp';
import { v4 as uuidv4 } from 'uuid';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use('/assets', express.static(path.join(__dirname, 'assets')));

// File storage configuration
const storage = multer.diskStorage({
    destination: async (req, file, cb) => {
        const uploadDir = path.join(__dirname, 'assets', 'frames');
        await fs.mkdir(uploadDir, { recursive: true });
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueName = `${uuidv4()}${path.extname(file.originalname)}`;
        cb(null, uniqueName);
    }
});

const upload = multer({
    storage,
    limits: { fileSize: 50 * 1024 * 1024 }, // 50MB limit
    fileFilter: (req, file, cb) => {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
        if (allowedTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error('Invalid file type. Only JPEG, PNG, WebP, and GIF are allowed.'));
        }
    }
});

// Database (JSON file for simplicity - use a real DB in production)
const DB_PATH = path.join(__dirname, 'data', 'frames.json');

async function loadDatabase() {
    try {
        const data = await fs.readFile(DB_PATH, 'utf-8');
        return JSON.parse(data);
    } catch {
        return { frames: [], tags: {}, metadata: { totalFrames: 0, lastUpdated: new Date().toISOString() } };
    }
}

async function saveDatabase(data) {
    await fs.mkdir(path.dirname(DB_PATH), { recursive: true });
    data.metadata.lastUpdated = new Date().toISOString();
    data.metadata.totalFrames = data.frames.length;
    await fs.writeFile(DB_PATH, JSON.stringify(data, null, 2));
}

// AI Analysis Functions
// In production, replace these with actual AI API calls

async function analyzeImageWithAI(imagePath) {
    // Simulated AI analysis
    // Replace with actual API calls to OpenAI Vision, Google Cloud Vision, etc.

    const possibleTags = {
        mood: ['mysterious', 'epic', 'dramatic', 'peaceful', 'intense', 'melancholic', 'hopeful', 'dark', 'bright'],
        lighting: ['natural', 'neon', 'golden-hour', 'low-key', 'high-key', 'silhouette', 'chiaroscuro', 'harsh', 'soft'],
        composition: ['wide-shot', 'close-up', 'medium-shot', 'extreme-wide', 'over-shoulder', 'dutch-angle', 'symmetrical'],
        setting: ['urban', 'nature', 'interior', 'desert', 'ocean', 'forest', 'industrial', 'space', 'suburban'],
        color: ['warm', 'cool', 'monochrome', 'vibrant', 'muted', 'neon', 'earth-tones', 'pastel']
    };

    const selectRandom = (arr, count) => {
        const shuffled = [...arr].sort(() => 0.5 - Math.random());
        return shuffled.slice(0, count);
    };

    // Extract color palette using sharp
    let colorPalette = [];
    try {
        const stats = await sharp(imagePath).stats();
        // Use channel means to generate approximate colors
        const r = Math.round(stats.channels[0].mean);
        const g = Math.round(stats.channels[1].mean);
        const b = Math.round(stats.channels[2].mean);
        colorPalette = [
            `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`,
            `#${Math.max(0, r - 40).toString(16).padStart(2, '0')}${Math.max(0, g - 40).toString(16).padStart(2, '0')}${Math.max(0, b - 40).toString(16).padStart(2, '0')}`,
            `#${Math.min(255, r + 40).toString(16).padStart(2, '0')}${Math.min(255, g + 40).toString(16).padStart(2, '0')}${Math.min(255, b + 40).toString(16).padStart(2, '0')}`,
            '#1a1a2e'
        ];
    } catch (err) {
        colorPalette = ['#6366f1', '#1a1a2e', '#ffffff', '#000000'];
    }

    const tags = [
        ...selectRandom(possibleTags.mood, 2),
        ...selectRandom(possibleTags.lighting, 1),
        ...selectRandom(possibleTags.composition, 1),
        ...selectRandom(possibleTags.setting, 1),
        ...selectRandom(possibleTags.color, 1)
    ];

    return {
        tags,
        mood: selectRandom(possibleTags.mood, 2),
        lighting: selectRandom(possibleTags.lighting, 2),
        composition: selectRandom(possibleTags.composition, 1)[0],
        colorPalette,
        dominantColors: selectRandom(['warm', 'cool', 'neutral'], 1),
        aiDescription: `A ${tags[0]} scene featuring ${tags[2]} lighting with a ${tags[3]} composition. The setting appears ${tags[4]} with ${tags[5]} color tones.`,
        embeddings: Array.from({ length: 8 }, () => Math.random()), // Placeholder for vector embeddings
        confidence: 0.85 + Math.random() * 0.14
    };
}

// Generate thumbnail
async function generateThumbnail(inputPath, outputPath) {
    await sharp(inputPath)
        .resize(400, 225, { fit: 'cover' })
        .jpeg({ quality: 85 })
        .toFile(outputPath);
}

// API Routes

// Get all frames with optional filtering
app.get('/api/frames', async (req, res) => {
    try {
        const db = await loadDatabase();
        let frames = db.frames;

        // Search query
        if (req.query.q) {
            const query = req.query.q.toLowerCase();
            frames = frames.filter(frame => {
                const searchable = [
                    frame.title,
                    frame.source,
                    frame.director,
                    frame.aiDescription,
                    ...frame.tags,
                    ...frame.mood,
                    ...frame.lighting
                ].join(' ').toLowerCase();
                return searchable.includes(query);
            });
        }

        // Tag filtering
        if (req.query.tags) {
            const filterTags = req.query.tags.split(',');
            frames = frames.filter(frame =>
                filterTags.some(tag => frame.tags.includes(tag))
            );
        }

        // Mood filtering
        if (req.query.mood) {
            const filterMood = req.query.mood.split(',');
            frames = frames.filter(frame =>
                filterMood.some(mood => frame.mood.includes(mood))
            );
        }

        // Pagination
        const page = parseInt(req.query.page) || 1;
        const limit = parseInt(req.query.limit) || 20;
        const startIndex = (page - 1) * limit;
        const endIndex = page * limit;

        const paginatedFrames = frames.slice(startIndex, endIndex);

        res.json({
            frames: paginatedFrames,
            total: frames.length,
            page,
            totalPages: Math.ceil(frames.length / limit)
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Get single frame
app.get('/api/frames/:id', async (req, res) => {
    try {
        const db = await loadDatabase();
        const frame = db.frames.find(f => f.id === req.params.id);

        if (!frame) {
            return res.status(404).json({ error: 'Frame not found' });
        }

        res.json(frame);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Upload new frame
app.post('/api/frames', upload.single('image'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'No image file provided' });
        }

        const db = await loadDatabase();

        // Generate thumbnail
        const thumbnailDir = path.join(__dirname, 'assets', 'thumbnails');
        await fs.mkdir(thumbnailDir, { recursive: true });
        const thumbnailFilename = `thumb_${req.file.filename}`;
        const thumbnailPath = path.join(thumbnailDir, thumbnailFilename);
        await generateThumbnail(req.file.path, thumbnailPath);

        // Analyze image with AI
        const analysis = await analyzeImageWithAI(req.file.path);

        // Create frame object
        const frame = {
            id: uuidv4(),
            filename: req.file.filename,
            originalName: req.file.originalname,
            title: req.body.title || req.file.originalname.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '),
            source: req.body.source || 'Unknown',
            sourceType: req.body.sourceType || 'movie',
            year: parseInt(req.body.year) || new Date().getFullYear(),
            director: req.body.director || 'Unknown',
            cinematographer: req.body.cinematographer || 'Unknown',
            tags: analysis.tags,
            mood: analysis.mood,
            lighting: analysis.lighting,
            colorPalette: analysis.colorPalette,
            dominantColors: analysis.dominantColors,
            composition: analysis.composition,
            aspectRatio: '16:9', // Could calculate from image dimensions
            aiDescription: analysis.aiDescription,
            embeddings: analysis.embeddings,
            thumbnail: `/assets/thumbnails/${thumbnailFilename}`,
            fullImage: `/assets/frames/${req.file.filename}`,
            downloads: 0,
            uploadedAt: new Date().toISOString()
        };

        db.frames.push(frame);
        await saveDatabase(db);

        res.status(201).json(frame);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Update frame
app.put('/api/frames/:id', async (req, res) => {
    try {
        const db = await loadDatabase();
        const index = db.frames.findIndex(f => f.id === req.params.id);

        if (index === -1) {
            return res.status(404).json({ error: 'Frame not found' });
        }

        const allowedUpdates = ['title', 'source', 'sourceType', 'year', 'director', 'cinematographer', 'tags', 'mood', 'lighting'];
        const updates = {};

        for (const key of allowedUpdates) {
            if (req.body[key] !== undefined) {
                updates[key] = req.body[key];
            }
        }

        db.frames[index] = { ...db.frames[index], ...updates, updatedAt: new Date().toISOString() };
        await saveDatabase(db);

        res.json(db.frames[index]);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Delete frame
app.delete('/api/frames/:id', async (req, res) => {
    try {
        const db = await loadDatabase();
        const index = db.frames.findIndex(f => f.id === req.params.id);

        if (index === -1) {
            return res.status(404).json({ error: 'Frame not found' });
        }

        const frame = db.frames[index];

        // Delete files
        try {
            await fs.unlink(path.join(__dirname, 'assets', 'frames', frame.filename));
            await fs.unlink(path.join(__dirname, frame.thumbnail));
        } catch {
            // Files might not exist, continue anyway
        }

        db.frames.splice(index, 1);
        await saveDatabase(db);

        res.json({ message: 'Frame deleted successfully' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Track download
app.post('/api/frames/:id/download', async (req, res) => {
    try {
        const db = await loadDatabase();
        const frame = db.frames.find(f => f.id === req.params.id);

        if (!frame) {
            return res.status(404).json({ error: 'Frame not found' });
        }

        frame.downloads = (frame.downloads || 0) + 1;
        await saveDatabase(db);

        res.json({ downloads: frame.downloads });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Find similar frames (using tag similarity, replace with vector similarity in production)
app.get('/api/frames/:id/similar', async (req, res) => {
    try {
        const db = await loadDatabase();
        const frame = db.frames.find(f => f.id === req.params.id);

        if (!frame) {
            return res.status(404).json({ error: 'Frame not found' });
        }

        // Calculate similarity based on tag overlap
        const similarFrames = db.frames
            .filter(f => f.id !== frame.id)
            .map(f => {
                const tagOverlap = f.tags.filter(t => frame.tags.includes(t)).length;
                const moodOverlap = f.mood.filter(m => frame.mood.includes(m)).length;
                const lightingOverlap = f.lighting.filter(l => frame.lighting.includes(l)).length;
                const similarity = (tagOverlap * 2 + moodOverlap * 3 + lightingOverlap * 2) /
                    (frame.tags.length + frame.mood.length + frame.lighting.length);
                return { ...f, similarity };
            })
            .sort((a, b) => b.similarity - a.similarity)
            .slice(0, parseInt(req.query.limit) || 6);

        res.json(similarFrames);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Get all available tags
app.get('/api/tags', async (req, res) => {
    try {
        const db = await loadDatabase();

        // Aggregate all unique tags from frames
        const allTags = {
            tags: [...new Set(db.frames.flatMap(f => f.tags))],
            moods: [...new Set(db.frames.flatMap(f => f.mood))],
            lighting: [...new Set(db.frames.flatMap(f => f.lighting))],
            compositions: [...new Set(db.frames.map(f => f.composition))]
        };

        res.json(allTags);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// AI-powered search endpoint
app.get('/api/search/ai', async (req, res) => {
    try {
        const query = req.query.q;
        if (!query) {
            return res.status(400).json({ error: 'Query parameter required' });
        }

        // Analyze the search query to extract semantic meaning
        const q = query.toLowerCase();
        const analysis = {
            mood: [],
            lighting: [],
            setting: [],
            color: []
        };

        // Mood detection
        if (q.includes('dark') || q.includes('moody') || q.includes('mysterious')) analysis.mood.push('mysterious', 'dark');
        if (q.includes('epic') || q.includes('grand') || q.includes('vast')) analysis.mood.push('epic', 'vast');
        if (q.includes('intense') || q.includes('action')) analysis.mood.push('intense', 'dramatic');
        if (q.includes('peaceful') || q.includes('calm')) analysis.mood.push('peaceful', 'contemplative');

        // Lighting detection
        if (q.includes('neon') || q.includes('glow') || q.includes('cyberpunk')) analysis.lighting.push('neon', 'artificial');
        if (q.includes('natural') || q.includes('daylight')) analysis.lighting.push('natural', 'golden-hour');
        if (q.includes('dark') || q.includes('shadow')) analysis.lighting.push('low-key');

        // Setting detection
        if (q.includes('city') || q.includes('urban')) analysis.setting.push('urban');
        if (q.includes('desert') || q.includes('sand')) analysis.setting.push('desert');
        if (q.includes('space') || q.includes('cosmic')) analysis.setting.push('space');
        if (q.includes('nature') || q.includes('forest')) analysis.setting.push('nature', 'forest');

        res.json({
            query,
            analysis,
            suggestions: [...analysis.mood, ...analysis.lighting, ...analysis.setting, ...analysis.color]
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Bulk upload endpoint
app.post('/api/frames/bulk', upload.array('images', 50), async (req, res) => {
    try {
        if (!req.files || req.files.length === 0) {
            return res.status(400).json({ error: 'No image files provided' });
        }

        const db = await loadDatabase();
        const results = [];

        for (const file of req.files) {
            try {
                // Generate thumbnail
                const thumbnailDir = path.join(__dirname, 'assets', 'thumbnails');
                await fs.mkdir(thumbnailDir, { recursive: true });
                const thumbnailFilename = `thumb_${file.filename}`;
                const thumbnailPath = path.join(thumbnailDir, thumbnailFilename);
                await generateThumbnail(file.path, thumbnailPath);

                // Analyze image
                const analysis = await analyzeImageWithAI(file.path);

                const frame = {
                    id: uuidv4(),
                    filename: file.filename,
                    originalName: file.originalname,
                    title: file.originalname.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '),
                    source: 'Unknown',
                    sourceType: 'movie',
                    year: new Date().getFullYear(),
                    director: 'Unknown',
                    cinematographer: 'Unknown',
                    tags: analysis.tags,
                    mood: analysis.mood,
                    lighting: analysis.lighting,
                    colorPalette: analysis.colorPalette,
                    dominantColors: analysis.dominantColors,
                    composition: analysis.composition,
                    aspectRatio: '16:9',
                    aiDescription: analysis.aiDescription,
                    embeddings: analysis.embeddings,
                    thumbnail: `/assets/thumbnails/${thumbnailFilename}`,
                    fullImage: `/assets/frames/${file.filename}`,
                    downloads: 0,
                    uploadedAt: new Date().toISOString()
                };

                db.frames.push(frame);
                results.push({ success: true, frame });
            } catch (error) {
                results.push({ success: false, filename: file.originalname, error: error.message });
            }
        }

        await saveDatabase(db);

        res.status(201).json({
            total: req.files.length,
            successful: results.filter(r => r.success).length,
            failed: results.filter(r => !r.success).length,
            results
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Start server
app.listen(PORT, () => {
    console.log(`
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   FrameVault Server Running                                  ║
║   http://localhost:${PORT}                                       ║
║                                                              ║
║   API Endpoints:                                             ║
║   GET    /api/frames          - List all frames              ║
║   GET    /api/frames/:id      - Get single frame             ║
║   POST   /api/frames          - Upload new frame             ║
║   PUT    /api/frames/:id      - Update frame                 ║
║   DELETE /api/frames/:id      - Delete frame                 ║
║   GET    /api/frames/:id/similar - Find similar frames       ║
║   GET    /api/tags            - Get all tags                 ║
║   GET    /api/search/ai       - AI-powered search            ║
║   POST   /api/frames/bulk     - Bulk upload                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    `);
});

export default app;
