---
name: image-processing-patterns
description: "Patrones para procesamiento de imágenes: resize, compress, thumbnails, watermarks."
type: feature
---

# Image Processing Patterns

## Descripción

Esta skill cubre procesamiento de imágenes del lado del servidor usando Sharp, Jimp, y servicios cloud como Cloudinary.

---

## Sharp (Recomendado para Node.js)

### Setup

```bash
npm install sharp
```

### Operaciones Básicas

```typescript
import sharp from 'sharp';

// Resize
async function resizeImage(
  input: Buffer,
  width: number,
  height?: number
): Promise<Buffer> {
  return sharp(input)
    .resize(width, height, {
      fit: 'inside',
      withoutEnlargement: true,
    })
    .toBuffer();
}

// Resize con aspect ratio
async function resizeWithAspectRatio(
  input: Buffer,
  maxWidth: number,
  maxHeight: number
): Promise<Buffer> {
  return sharp(input)
    .resize(maxWidth, maxHeight, {
      fit: 'inside',
      withoutEnlargement: true,
    })
    .toBuffer();
}

// Crop (cover)
async function cropToSize(
  input: Buffer,
  width: number,
  height: number
): Promise<Buffer> {
  return sharp(input)
    .resize(width, height, {
      fit: 'cover',
      position: 'center',
    })
    .toBuffer();
}

// Thumbnail
async function generateThumbnail(
  input: Buffer,
  size: number = 150
): Promise<Buffer> {
  return sharp(input)
    .resize(size, size, {
      fit: 'cover',
      position: 'entropy', // Smart crop
    })
    .toBuffer();
}
```

### Compresión y Conversión

```typescript
// Optimizar JPEG
async function optimizeJPEG(input: Buffer, quality: number = 80): Promise<Buffer> {
  return sharp(input)
    .jpeg({
      quality,
      progressive: true,
      mozjpeg: true,
    })
    .toBuffer();
}

// Convertir a WebP
async function convertToWebP(input: Buffer, quality: number = 80): Promise<Buffer> {
  return sharp(input)
    .webp({
      quality,
      effort: 6,
    })
    .toBuffer();
}

// Convertir a AVIF (mejor compresión)
async function convertToAVIF(input: Buffer, quality: number = 60): Promise<Buffer> {
  return sharp(input)
    .avif({
      quality,
      effort: 6,
    })
    .toBuffer();
}

// Generar múltiples formatos
async function generateResponsiveFormats(input: Buffer) {
  const [jpeg, webp, avif] = await Promise.all([
    sharp(input).jpeg({ quality: 80, mozjpeg: true }).toBuffer(),
    sharp(input).webp({ quality: 80 }).toBuffer(),
    sharp(input).avif({ quality: 60 }).toBuffer(),
  ]);

  return { jpeg, webp, avif };
}
```

### Watermark

```typescript
async function addWatermark(
  input: Buffer,
  watermarkPath: string,
  position: 'center' | 'bottom-right' = 'bottom-right'
): Promise<Buffer> {
  const image = sharp(input);
  const metadata = await image.metadata();

  const watermark = await sharp(watermarkPath)
    .resize(Math.round(metadata.width! * 0.2))
    .toBuffer();

  const gravity = position === 'center' ? 'center' : 'southeast';

  return image
    .composite([
      {
        input: watermark,
        gravity,
        blend: 'over',
      },
    ])
    .toBuffer();
}

// Watermark de texto
async function addTextWatermark(
  input: Buffer,
  text: string
): Promise<Buffer> {
  const image = sharp(input);
  const metadata = await image.metadata();

  const svgText = `
    <svg width="${metadata.width}" height="50">
      <text x="50%" y="50%"
            font-family="Arial"
            font-size="20"
            fill="white"
            fill-opacity="0.5"
            text-anchor="middle"
            dominant-baseline="middle">
        ${text}
      </text>
    </svg>
  `;

  return image
    .composite([
      {
        input: Buffer.from(svgText),
        gravity: 'south',
      },
    ])
    .toBuffer();
}
```

### Pipeline Completo

```typescript
interface ProcessedImage {
  original: { buffer: Buffer; metadata: sharp.Metadata };
  thumbnail: Buffer;
  medium: Buffer;
  large: Buffer;
  webp: Buffer;
}

async function processUploadedImage(input: Buffer): Promise<ProcessedImage> {
  const pipeline = sharp(input).rotate(); // Auto-rotate based on EXIF

  const metadata = await pipeline.metadata();

  const [thumbnail, medium, large, webp] = await Promise.all([
    // Thumbnail 150x150
    pipeline.clone()
      .resize(150, 150, { fit: 'cover' })
      .jpeg({ quality: 80 })
      .toBuffer(),

    // Medium 800px
    pipeline.clone()
      .resize(800, null, { withoutEnlargement: true })
      .jpeg({ quality: 85 })
      .toBuffer(),

    // Large 1920px
    pipeline.clone()
      .resize(1920, null, { withoutEnlargement: true })
      .jpeg({ quality: 90 })
      .toBuffer(),

    // WebP optimizado
    pipeline.clone()
      .resize(1200, null, { withoutEnlargement: true })
      .webp({ quality: 80 })
      .toBuffer(),
  ]);

  return {
    original: { buffer: await pipeline.toBuffer(), metadata },
    thumbnail,
    medium,
    large,
    webp,
  };
}
```

---

## Cloudinary (SaaS)

### Setup

```typescript
import { v2 as cloudinary } from 'cloudinary';

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});
```

### Upload y Transformaciones

```typescript
// Upload con transformación automática
async function uploadImage(filePath: string) {
  return cloudinary.uploader.upload(filePath, {
    folder: 'products',
    transformation: [
      { width: 1000, height: 1000, crop: 'limit' },
      { quality: 'auto:good' },
      { fetch_format: 'auto' },
    ],
    eager: [
      { width: 300, height: 300, crop: 'fill' },
      { width: 150, height: 150, crop: 'thumb', gravity: 'face' },
    ],
  });
}

// URL con transformación on-the-fly
function getImageURL(publicId: string, options: ImageOptions) {
  return cloudinary.url(publicId, {
    width: options.width,
    height: options.height,
    crop: options.crop || 'fill',
    quality: 'auto',
    fetch_format: 'auto',
    secure: true,
  });
}

// Ejemplos de URLs
const thumbnail = getImageURL('products/abc123', { width: 150, height: 150 });
// https://res.cloudinary.com/demo/image/upload/w_150,h_150,c_fill,q_auto,f_auto/products/abc123

const responsive = getImageURL('products/abc123', { width: 800 });
// Automáticamente sirve WebP/AVIF según el navegador
```

---

## API de Imágenes

```typescript
import { Router } from 'express';
import multer from 'multer';
import sharp from 'sharp';

const router = Router();
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('image/')) {
      cb(null, true);
    } else {
      cb(new Error('Only images allowed'));
    }
  },
});

router.post('/upload', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No image provided' });
    }

    const processed = await processUploadedImage(req.file.buffer);

    // Guardar en storage (S3, etc.)
    const urls = await saveToStorage(processed);

    res.json({
      success: true,
      urls,
      metadata: processed.original.metadata,
    });
  } catch (error) {
    console.error('Image processing failed:', error);
    res.status(500).json({ error: 'Failed to process image' });
  }
});

// Resize on-the-fly
router.get('/images/:id', async (req, res) => {
  const { width, height, format } = req.query;

  const image = await getImageFromStorage(req.params.id);

  let pipeline = sharp(image);

  if (width || height) {
    pipeline = pipeline.resize(
      width ? parseInt(width as string) : null,
      height ? parseInt(height as string) : null,
      { fit: 'inside', withoutEnlargement: true }
    );
  }

  if (format === 'webp') {
    pipeline = pipeline.webp({ quality: 80 });
    res.type('image/webp');
  } else {
    pipeline = pipeline.jpeg({ quality: 85 });
    res.type('image/jpeg');
  }

  pipeline.pipe(res);
});
```

---

## Validación de Imágenes

```typescript
async function validateImage(buffer: Buffer): Promise<ValidationResult> {
  try {
    const metadata = await sharp(buffer).metadata();

    const errors: string[] = [];

    // Validar formato
    const allowedFormats = ['jpeg', 'png', 'webp', 'gif'];
    if (!allowedFormats.includes(metadata.format!)) {
      errors.push(`Format ${metadata.format} not allowed`);
    }

    // Validar dimensiones mínimas
    if (metadata.width! < 100 || metadata.height! < 100) {
      errors.push('Image too small (min 100x100)');
    }

    // Validar dimensiones máximas
    if (metadata.width! > 10000 || metadata.height! > 10000) {
      errors.push('Image too large (max 10000x10000)');
    }

    // Validar aspect ratio
    const aspectRatio = metadata.width! / metadata.height!;
    if (aspectRatio > 10 || aspectRatio < 0.1) {
      errors.push('Invalid aspect ratio');
    }

    return {
      valid: errors.length === 0,
      errors,
      metadata,
    };
  } catch {
    return {
      valid: false,
      errors: ['Invalid image file'],
    };
  }
}
```

---

## Referencias

- [Sharp Documentation](https://sharp.pixelplumbing.com/)
- [Cloudinary Docs](https://cloudinary.com/documentation)
- [ImageMagick](https://imagemagick.org/)
- [Web Image Optimization](https://web.dev/fast/#optimize-your-images)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
