"""
Image Generator Module for Paper Storyteller

Generates images for paper visualization using:
1. Imagen 4.0 (primary) - for high quality images
2. Gemini native image generation (fallback)

Supported image types:
- Pipeline diagrams
- Architecture visualizations
- Comparison charts
- Concept illustrations
"""

from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger
import base64
import hashlib

from google import genai
from google.genai import types


class ImageGenerator:
    """Generate images for paper storytelling using Google AI"""
    
    def __init__(self, api_key: str, output_dir: str = "output/images"):
        """
        Initialize the image generator
        
        Args:
            api_key: Google API key
            output_dir: Directory to save generated images
        """
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize client
        self.client = genai.Client(api_key=api_key)
        
        logger.info(f"🎨 ImageGenerator initialized, output dir: {self.output_dir}")
    
    def _get_cache_path(self, prompt: str, prefix: str = "img") -> Path:
        """Get cache path for a prompt to avoid regenerating"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:12]
        return self.output_dir / f"{prefix}_{prompt_hash}.png"
    
    def generate_with_imagen(self, prompt: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        Generate image using Imagen 4.0
        
        Args:
            prompt: Text description of the image
            filename: Optional custom filename
            
        Returns:
            Path to generated image or None if failed
        """
        try:
            logger.info(f"🖼️ Generating image with Imagen: {prompt[:50]}...")
            
            response = self.client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type='image/png',
                ),
            )
            
            if response.generated_images:
                img = response.generated_images[0].image
                
                # Determine filename
                if filename:
                    img_path = self.output_dir / filename
                else:
                    img_path = self._get_cache_path(prompt, "imagen")
                
                img.save(str(img_path))
                logger.success(f"✅ Imagen image saved: {img_path}")
                return img_path
            
            logger.warning("❌ Imagen returned no images")
            return None
            
        except Exception as e:
            logger.error(f"❌ Imagen error: {e}")
            return None
    
    def generate_with_gemini(self, prompt: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        Generate image using Gemini native image generation
        
        Args:
            prompt: Text description of the image
            filename: Optional custom filename
            
        Returns:
            Path to generated image or None if failed
        """
        try:
            logger.info(f"🎨 Generating image with Gemini: {prompt[:50]}...")
            
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp-image-generation',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE', 'TEXT']
                )
            )
            
            # Extract image from response
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        img_data = part.inline_data.data
                        
                        # Determine filename
                        if filename:
                            img_path = self.output_dir / filename
                        else:
                            img_path = self._get_cache_path(prompt, "gemini")
                        
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                        
                        logger.success(f"✅ Gemini image saved: {img_path}")
                        return img_path
            
            logger.warning("❌ Gemini returned no image")
            return None
            
        except Exception as e:
            logger.error(f"❌ Gemini image error: {e}")
            return None
    
    def generate(self, prompt: str, filename: Optional[str] = None, 
                 prefer_imagen: bool = True) -> Optional[Path]:
        """
        Generate image with automatic fallback
        
        Args:
            prompt: Text description
            filename: Optional custom filename
            prefer_imagen: If True, try Imagen first, then Gemini
            
        Returns:
            Path to generated image or None
        """
        # Check cache first
        cache_path = self._get_cache_path(prompt)
        if cache_path.exists():
            logger.info(f"📦 Using cached image: {cache_path}")
            return cache_path
        
        if prefer_imagen:
            result = self.generate_with_imagen(prompt, filename)
            if result:
                return result
            logger.info("Falling back to Gemini...")
            return self.generate_with_gemini(prompt, filename)
        else:
            result = self.generate_with_gemini(prompt, filename)
            if result:
                return result
            logger.info("Falling back to Imagen...")
            return self.generate_with_imagen(prompt, filename)
    
    # ==========================================================================
    # Paper-specific image generation methods
    # ==========================================================================
    
    def generate_pipeline_diagram(self, paper_title: str, 
                                   architecture_description: str) -> Optional[Path]:
        """
        Generate a pipeline/architecture diagram for a paper
        
        Args:
            paper_title: Title of the paper
            architecture_description: Description of the architecture
            
        Returns:
            Path to generated diagram
        """
        prompt = f"""Create a clean, professional technical diagram for the AI paper "{paper_title}".

The diagram should show:
{architecture_description}

Style requirements:
- Clean, minimalist design
- White or light gray background
- Use blue, purple, and orange accent colors
- Clear labels and arrows showing data flow
- Professional, publication-quality appearance
- No text overlapping
- Modern flat design style

The diagram should be educational and easy to understand for students."""

        return self.generate(prompt, filename=f"pipeline_{hashlib.md5(paper_title.encode()).hexdigest()[:8]}.png")
    
    def generate_comparison_image(self, title: str, 
                                   comparison_points: List[Dict]) -> Optional[Path]:
        """
        Generate a comparison visualization (e.g., before/after, method A vs B)
        
        Args:
            title: Title of the comparison
            comparison_points: List of comparison items
            
        Returns:
            Path to generated image
        """
        points_text = "\n".join([
            f"- {p.get('name', 'Item')}: {p.get('description', '')}"
            for p in comparison_points
        ])
        
        prompt = f"""Create a side-by-side comparison diagram titled "{title}".

Show:
{points_text}

Style:
- Split screen or card layout
- Use contrasting colors (red for old/problem, green for new/solution)
- Clear visual icons or illustrations
- Clean, modern design
- Easy to understand at a glance
- Educational and engaging for teenagers"""

        return self.generate(prompt, filename=f"comparison_{hashlib.md5(title.encode()).hexdigest()[:8]}.png")
    
    def generate_concept_illustration(self, concept: str, 
                                       metaphor: str = None) -> Optional[Path]:
        """
        Generate an illustration explaining a concept
        
        Args:
            concept: The AI/ML concept to illustrate
            metaphor: Optional metaphor to use
            
        Returns:
            Path to generated image
        """
        if metaphor:
            prompt = f"""Create an educational illustration explaining "{concept}" using the metaphor of "{metaphor}".

Requirements:
- Visual metaphor that makes the concept intuitive
- Colorful and engaging for young students
- Clean, modern illustration style
- Include visual elements that represent both the metaphor and the technical concept
- Avoid text, let the image speak"""
        else:
            prompt = f"""Create an educational illustration explaining the AI concept "{concept}".

Requirements:
- Simple, intuitive visualization
- Colorful and engaging for young students
- Shows the key idea visually
- Modern, clean illustration style
- Suitable for educational materials"""

        return self.generate(prompt, filename=f"concept_{hashlib.md5(concept.encode()).hexdigest()[:8]}.png")
    
    def generate_application_scenario(self, application: str, 
                                       domain: str) -> Optional[Path]:
        """
        Generate an image showing real-world application
        
        Args:
            application: What the AI does
            domain: Application domain (medical, autonomous driving, etc.)
            
        Returns:
            Path to generated image
        """
        prompt = f"""Create an illustration showing AI technology being used for "{application}" in the {domain} field.

Requirements:
- Show a realistic scenario where this technology helps people
- Include both the technology elements and human users
- Optimistic, positive tone
- Modern, professional illustration style
- Suitable for educational content about AI applications"""

        return self.generate(prompt, filename=f"app_{domain}_{hashlib.md5(application.encode()).hexdigest()[:8]}.png")
    
    def generate_hero_image(self, paper_title: str, 
                            main_contribution: str) -> Optional[Path]:
        """
        Generate a hero/banner image for the article
        
        Args:
            paper_title: Title of the paper
            main_contribution: Main contribution of the paper
            
        Returns:
            Path to generated image
        """
        prompt = f"""Create a stunning hero banner image for an AI research article about "{paper_title}".

Main theme: {main_contribution}

Requirements:
- Wide aspect ratio (16:9 or similar)
- Visually striking and professional
- Abstract or semi-abstract representation of the concept
- Use a gradient color scheme (blue to purple or similar)
- Modern, futuristic feel
- Suitable as a website header image
- No text in the image"""

        return self.generate(prompt, filename=f"hero_{hashlib.md5(paper_title.encode()).hexdigest()[:8]}.png")
    
    def generate_all_paper_images(self, metadata: Dict, 
                                   architecture_desc: str = None) -> Dict[str, Path]:
        """
        Generate all images needed for a paper article
        
        Args:
            metadata: Paper metadata (title, abstract, etc.)
            architecture_desc: Description of the architecture
            
        Returns:
            Dictionary of image type -> path
        """
        images = {}
        
        title = metadata.get('title', 'AI Paper')
        abstract = metadata.get('abstract', '')[:300]
        
        logger.info(f"🎨 Generating images for: {title[:50]}...")
        
        # 1. Hero image
        logger.info("  [1/4] Generating hero image...")
        hero = self.generate_hero_image(title, abstract)
        if hero:
            images['hero'] = hero
        
        # 2. Pipeline diagram
        if architecture_desc:
            logger.info("  [2/4] Generating pipeline diagram...")
            pipeline = self.generate_pipeline_diagram(title, architecture_desc)
            if pipeline:
                images['pipeline'] = pipeline
        
        # 3. Concept illustration
        logger.info("  [3/4] Generating concept illustration...")
        concept = self.generate_concept_illustration(
            f"Key innovation from {title}", 
            "a breakthrough in AI understanding"
        )
        if concept:
            images['concept'] = concept
        
        # 4. Application scenario
        logger.info("  [4/4] Generating application image...")
        app = self.generate_application_scenario(
            f"AI technology from {title}",
            "robotics and automation"
        )
        if app:
            images['application'] = app
        
        logger.success(f"✅ Generated {len(images)} images for the paper")
        return images


def image_to_base64(image_path: Path) -> str:
    """Convert image to base64 for HTML embedding"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def embed_image_html(image_path: Path, alt_text: str = "Generated image") -> str:
    """Generate HTML img tag with embedded base64 image"""
    b64 = image_to_base64(image_path)
    return f'<img src="data:image/png;base64,{b64}" alt="{alt_text}" style="max-width: 100%; height: auto;">'


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    import os
    from .utils import setup_logging
    
    setup_logging("INFO")
    
    # Get API key from environment variable
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not API_KEY:
        print("❌ Please set GOOGLE_API_KEY environment variable")
        exit(1)
    
    generator = ImageGenerator(API_KEY, output_dir="test_images")
    
    # Test hero image generation
    print("\n🎨 Testing hero image generation...")
    hero = generator.generate_hero_image(
        "OneFormer3D: One Transformer for Unified Point Cloud Segmentation",
        "A unified transformer architecture for 3D segmentation"
    )
    
    if hero:
        print(f"✅ Hero image saved to: {hero}")
    else:
        print("❌ Failed to generate hero image")
    
    # Test pipeline diagram
    print("\n🎨 Testing pipeline diagram generation...")
    pipeline = generator.generate_pipeline_diagram(
        "OneFormer3D",
        """
        - Input: 3D point cloud (LiDAR scan)
        - Encoder: Transformer-based feature extraction
        - Unified Query: Single set of learnable queries
        - Decoder: Three-way segmentation heads
        - Output: Semantic, instance, and panoptic segmentation
        """
    )
    
    if pipeline:
        print(f"✅ Pipeline diagram saved to: {pipeline}")
    else:
        print("❌ Failed to generate pipeline diagram")
    
    print("\n🎉 Image generation test complete!")
