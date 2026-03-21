document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('creator-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('loader');
    const errorMsg = document.getElementById('error-message');
    
    const emptyState = document.getElementById('empty-state');
    const resultsContent = document.getElementById('results-content');
    const postsContainer = document.getElementById('posts-container');
    const metaBrand = document.getElementById('meta-brand');
    const metaSummary = document.getElementById('meta-summary');
    const csvBar = document.getElementById('csv-bar');
    
    // Show/hide custom RSS URL when toggle is flipped
    const trendingNewsToggle = document.getElementById('use_trending_news');
    const feedUrlGroup = document.getElementById('feed-url-group');
    trendingNewsToggle.addEventListener('change', () => {
        feedUrlGroup.style.display = trendingNewsToggle.checked ? 'block' : 'none';
    });
    
    // Tab switching logic for separate tab groups
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Find the parent container of this group of tabs to isolate the toggle
            const tabGroup = tab.closest('.tabs');
            if (!tabGroup) return;

            // Remove active from sibling tabs only
            tabGroup.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Toggle the content based on data-target
            const targetId = tab.dataset.target;
            
            // If it's the mode tabs (Manual vs Factory)
            if (targetId.startsWith('mode-')) {
                document.querySelectorAll('.mode-content').forEach(tc => tc.style.display = 'none');
                document.getElementById(targetId).style.display = 'block';
            } else {
                // If it's the result tabs (Posts vs Meta vs Email)
                document.querySelectorAll('.results-panel .tab-content').forEach(tc => tc.classList.remove('active'));
                document.getElementById(targetId).classList.add('active');
            }
        });
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            brand_desc: document.getElementById('brand_desc').value,
            sample_posts: document.getElementById('sample_posts').value,
            pillar_text: document.getElementById('pillar_text').value,
            n_posts: parseInt(document.getElementById('n_posts').value, 10),
            use_trending_news: document.getElementById('use_trending_news').checked,
            feed_url: document.getElementById('feed_url').value || 'https://techcrunch.com/feed/'
        };
        
        // UI Loading state
        btnText.style.display = 'none';
        loader.style.display = 'block';
        submitBtn.disabled = true;
        errorMsg.style.display = 'none';
        
        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            let data;
            const resText = await response.text();
            
            if (!response.ok) {
                try {
                    const errData = JSON.parse(resText);
                    throw new Error(errData.detail || 'Failed to generate content');
                } catch (e) {
                    throw new Error(resText || 'Unknown Server Error (Empty Response)');
                }
            }
            
            try {
                data = JSON.parse(resText);
            } catch (e) {
                throw new Error('Invalid JSON received from server.');
            }
            
            // Display Data
            emptyState.style.display = 'none';
            resultsContent.style.display = 'block';
            
            // Render Meta Output
            metaBrand.textContent = JSON.stringify(data.brand_profile, null, 2);
            metaSummary.textContent = JSON.stringify(data.pillar_summary, null, 2);
            
            // Render Posts
            postsContainer.innerHTML = '';
            const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
            
            if (data.posts && data.posts.length > 0) {
                data.posts.forEach((post, index) => {
                    const delay = index * 0.1; // Stagger animation
                    const day = days[index % days.length];
                    
                    const el = document.createElement('div');
                    el.className = 'post-card';
                    el.style.animationDelay = `${delay}s`;
                    
                    let bodyContent = post.body || '';
                    if (post.hook) {
                        bodyContent = `<strong>${post.hook}</strong><br><br>${bodyContent}`;
                    }
                    if (post.CTA) {
                        bodyContent += `<br><br><span class="post-cta">${post.CTA}</span>`;
                    }
                    
                    el.innerHTML = `
                        <div class="post-header">
                            <div class="post-title">#${index + 1}: ${post.title || 'Post'} <span class="post-day-badge">${day}</span></div>
                            <div class="post-format">${post.format_hint || 'General'}</div>
                        </div>
                        <div class="post-content">${bodyContent.replace(/\n/g, '<br>')}</div>
                    `;
                    
                    postsContainer.appendChild(el);
                });

                csvBar.style.display = 'block';
                window._generatedPosts = data.posts;
            } else {
                postsContainer.innerHTML = '<p>No posts returned.</p>';
                csvBar.style.display = 'none';
            }
            
        } catch (error) {
            errorMsg.textContent = error.message;
            errorMsg.style.display = 'block';
            csvBar.style.display = 'none';
        } finally {
            // Restore UI
            btnText.style.display = 'block';
            loader.style.display = 'none';
            submitBtn.disabled = false;
        }
    });

    // CSV Download
    const downloadCsvBtn = document.getElementById('download-csv-btn');
    downloadCsvBtn.addEventListener('click', async () => {
        const posts = window._generatedPosts;
        if (!posts || posts.length === 0) return;

        const origText = downloadCsvBtn.textContent;
        downloadCsvBtn.textContent = 'Preparing...';
        downloadCsvBtn.disabled = true;

        try {
            const response = await fetch('/api/export-csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ posts })
            });

            if (!response.ok) throw new Error('CSV export failed');

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'linkedin_content_calendar.txt';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            downloadCsvBtn.textContent = 'Downloaded!';
            setTimeout(() => {
                downloadCsvBtn.textContent = origText;
                downloadCsvBtn.disabled = false;
            }, 3000);
        } catch (err) {
            downloadCsvBtn.textContent = 'Export Failed';
            downloadCsvBtn.disabled = false;
        }
    });

    // === Image Prompts Generator ===
    const genImagesBtn = document.getElementById('gen-images-btn');
    const genImagesText = document.getElementById('gen-images-text');
    const genImagesLoader = document.getElementById('gen-images-loader');
    const genImagesHint = document.getElementById('gen-images-hint');
    const imagePromptsContainer = document.getElementById('image-prompts-container');

    genImagesBtn.addEventListener('click', async () => {
        const posts = window._generatedPosts;
        if (!posts || posts.length === 0) {
            genImagesHint.textContent = 'Generate posts first, then come here for image prompts.';
            genImagesHint.style.color = '#ff4d4d';
            return;
        }

        // Loading state
        genImagesText.style.display = 'none';
        genImagesLoader.style.display = 'block';
        genImagesBtn.disabled = true;
        genImagesHint.textContent = 'Crafting visual prompts with AI... this takes ~20 seconds.';
        genImagesHint.style.color = '#a1a1aa';
        imagePromptsContainer.innerHTML = '';

        try {
            const response = await fetch('/api/image-prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ posts })
            });

            const resText = await response.text();
            if (!response.ok) {
                const err = JSON.parse(resText);
                throw new Error(err.detail || 'Failed to generate image prompts');
            }

            const data = JSON.parse(resText);
            const prompts = data.image_prompts || [];

            if (prompts.length === 0) {
                imagePromptsContainer.innerHTML = '<p style="color:#a1a1aa">No prompts returned. Try again.</p>';
                return;
            }

            const totalVariations = prompts.reduce((sum, p) => sum + (p.variations?.length || 1), 0);
            genImagesHint.textContent = `${totalVariations} image prompts across ${prompts.length} post${prompts.length > 1 ? 's' : ''}! Copy and paste into Midjourney or DALL-E.`;
            genImagesHint.style.color = '#6ee7b7';

            // Style config
            const styleConfig = {
                '3d render':        { color: '#7c3aed', emoji: '' },
                '3d':               { color: '#7c3aed', emoji: '' },
                'cinematic':        { color: '#b45309', emoji: '' },
                'cinematic photo':  { color: '#b45309', emoji: '' },
                'flat illustration':{ color: '#0369a1', emoji: '' },
                'illustration':     { color: '#0369a1', emoji: '' },
                'minimal':          { color: '#374151', emoji: '' },
            };

            const getStyle = (s) => {
                const key = Object.keys(styleConfig).find(k => (s||'').toLowerCase().includes(k));
                return key ? styleConfig[key] : { color: '#6b7280', emoji: '' };
            };

            prompts.forEach((item, idx) => {
                const card = document.createElement('div');
                card.className = 'prompt-card';
                card.style.animationDelay = `${idx * 0.12}s`;
                const postTitle = item.title || `Post #${item.post_number || idx + 1}`;

                // Build variation rows
                const variations = item.variations || (item.prompt
                    ? [{ style: item.style || 'General', prompt: item.prompt }]
                    : []);

                const variationHTML = variations.map((v, vi) => {
                    const cfg = getStyle(v.style);
                    const escapedPrompt = (v.prompt || '').replace(/"/g, '&quot;');
                    return `
                        <div class="variation-row">
                            <div class="variation-style-label" style="color:${cfg.color};">
                                ${v.style}
                            </div>
                            <div class="prompt-text">${v.prompt || ''}</div>
                            <button class="copy-prompt-btn" data-prompt="${escapedPrompt}">
                                Copy Prompt
                            </button>
                        </div>
                    `;
                }).join('<div class="variation-divider"></div>');

                card.innerHTML = `
                    <div class="prompt-header">
                        <div class="prompt-post-label">Post #${item.post_number || idx + 1}: ${postTitle}</div>
                        <span class="prompt-count-badge">${variations.length} styles</span>
                    </div>
                    ${variationHTML}
                `;
                imagePromptsContainer.appendChild(card);
            });

            // Wire up ALL copy buttons
            imagePromptsContainer.querySelectorAll('.copy-prompt-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const text = btn.getAttribute('data-prompt');
                    try {
                        await navigator.clipboard.writeText(text);
                        btn.textContent = 'Copied!';
                        setTimeout(() => { btn.textContent = 'Copy Prompt'; }, 2000);
                    } catch {
                        btn.textContent = 'Failed';
                    }
                });
            });

        } catch (error) {
            genImagesHint.textContent = 'Error: ' + error.message;
            genImagesHint.style.color = '#ff4d4d';
        } finally {
            genImagesText.style.display = 'block';
            genImagesLoader.style.display = 'none';
            genImagesBtn.disabled = false;
        }
    });

    // Handle Factory Trigger Button
    const triggerBtn = document.getElementById('trigger-btn');
    const triggerBtnText = document.getElementById('trigger-btn-text');
    const triggerLoader = document.getElementById('trigger-loader');
    const triggerMessage = document.getElementById('trigger-message');

    triggerBtn.addEventListener('click', async () => {
        const feedUrl = document.getElementById('trigger_feed').value;
        const targetEmail = document.getElementById('trigger_email').value;

        if (!feedUrl || !targetEmail) {
            triggerMessage.textContent = "Please provide both an RSS Feed and an Target Email Address.";
            triggerMessage.style.color = '#ff4d4d';
            return;
        }

        // UI Loading state
        triggerBtnText.style.display = 'none';
        triggerLoader.style.display = 'block';
        triggerBtn.disabled = true;
        triggerMessage.textContent = "Pipelines running... Scanning feed, injecting RAG context, and running local Llama 3.2. This could take up to 2 minutes...";
        triggerMessage.style.color = '#a1a1aa';

        try {
            const response = await fetch('/api/test-pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_feed: feedUrl, target_email: targetEmail })
            });
            
            let errData;
            const resText = await response.text();
            
            if (!response.ok) {
                try {
                    errData = JSON.parse(resText);
                    throw new Error(errData.detail || 'Failed to trigger pipeline');
                } catch (e) {
                    throw new Error(resText || 'Unknown Server Error (Empty Response from Backend)');
                }
            }
            
            let data;
            try {
                data = JSON.parse(resText);
            } catch (e) {
                throw new Error('Invalid JSON received from server.');
            }
            
            // Display Data in the Message Box
            triggerMessage.textContent = "Pipeline execution complete! Check the Email Draft tab.";
            triggerMessage.style.color = '#a7f3d0';

            // Show results UI
            emptyState.style.display = 'none';
            resultsContent.style.display = 'block';

            // Make the email tab visible and click it
            const emailTabBtn = document.getElementById('tab-email-btn');
            emailTabBtn.style.display = 'block';
            
            // Populate Email Mockup
            const emailBodyNode = document.getElementById('email-mock-body');
            const emailToNode = document.getElementById('email-mock-to');
            emailToNode.textContent = targetEmail;
            emailBodyNode.textContent = data.message;
            
            // Switch to Email tab automatically
            emailTabBtn.click();

        } catch (error) {
            triggerMessage.textContent = "Error: " + error.message;
            triggerMessage.style.color = '#ff4d4d';
        } finally {
            // Restore UI
            triggerBtnText.style.display = 'block';
            triggerLoader.style.display = 'none';
            triggerBtn.disabled = false;
        }
    });

    // Handle Sending the Actual Real Email
    const sendEmailBtn = document.getElementById('send-real-email-btn');
    const sendEmailText = document.getElementById('send-email-text');
    const sendEmailLoader = document.getElementById('send-email-loader');
    const sendEmailMessage = document.getElementById('send-email-message');

    sendEmailBtn.addEventListener('click', async () => {
        const targetEmail = document.getElementById('trigger_email').value;
        const emailBody = document.getElementById('email-mock-body').textContent;

        if (!targetEmail || !emailBody) {
            sendEmailMessage.textContent = "Error: Missing target email or email body.";
            sendEmailMessage.style.color = '#ff4d4d';
            return;
        }

        // Set Loading State
        sendEmailText.style.display = 'none';
        sendEmailLoader.style.display = 'block';
        sendEmailBtn.disabled = true;
        sendEmailMessage.textContent = "Connecting to SMTP server and dispatching email...";
        sendEmailMessage.style.color = '#64748b';

        try {
            const response = await fetch('/api/send-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    target_email: targetEmail,
                    body: emailBody
                })
            });
            
            let errData;
            const resText = await response.text();
            
            if (!response.ok) {
                try {
                    errData = JSON.parse(resText);
                    throw new Error(errData.detail || 'Failed to send email');
                } catch (e) {
                    throw new Error(resText || 'Unknown SMTP Server Error. Check server console.');
                }
            }
            
            let data;
            try {
                data = JSON.parse(resText);
            } catch (e) {
                throw new Error('Invalid JSON received from backend.');
            }
            
            // Show Success
            sendEmailMessage.textContent = data.message;
            sendEmailMessage.style.color = '#10b981'; // Green
            
            // Keep button disabled to avoid spam duplicates
            sendEmailBtn.style.background = '#10b981';
            sendEmailText.textContent = "Email Sent!";

        } catch (error) {
            sendEmailMessage.textContent = error.message;
            sendEmailMessage.style.color = '#ef4444'; // Red
            sendEmailBtn.disabled = false;
        } finally {
            sendEmailText.style.display = 'block';
            sendEmailLoader.style.display = 'none';
        }
    });

});

// --- Particle Background System ---
class ParticleSystem {
    constructor() {
        this.canvas = document.getElementById('particleCanvas');
        if (!this.canvas) return; // safety check
        this.ctx = this.canvas.getContext('2d');
        
        this.particles = [];
        this.numParticles = window.innerWidth < 768 ? 600 : 1200; // adaptive count based on screen size
        
        // Colors matching a dark AI-themed UI: blue, purple, light violet
        this.colors = ['#4c1d95', '#7b2cbf', '#9d4edd', '#c77dff', '#e0aaff', '#a9def9'];
        
        // Vanishing point (origin)
        this.centerX = window.innerWidth / 2;
        this.centerY = window.innerHeight / 2;
        
        // Mouse/target point for focal center
        this.mouse = {
            x: this.centerX,
            y: this.centerY,
            targetX: this.centerX,
            targetY: this.centerY,
            moving: false,
            speed: 0
        };
        
        this.resize();
        this.initParticles();
        this.bindEvents();
        this.animate();
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.centerX = window.innerWidth / 2;
        this.centerY = window.innerHeight / 2;
        
        // Update adaptive constraints on resize
        let newCount = window.innerWidth < 768 ? 600 : 1200;
        if (newCount !== this.numParticles) {
            this.numParticles = newCount;
            this.initParticles();
        }
    }
    
    bindEvents() {
        window.addEventListener('resize', () => {
            // Debounce resize
            clearTimeout(this.resizeTimeout);
            this.resizeTimeout = setTimeout(() => this.resize(), 200);
        });
        
        window.addEventListener('mousemove', (e) => {
            this.mouse.targetX = e.clientX;
            this.mouse.targetY = e.clientY;
            this.mouse.moving = true;
            clearTimeout(this.mouseTimeout);
            this.mouseTimeout = setTimeout(() => {
                this.mouse.moving = false;
            }, 100);
        });
        
        window.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                this.mouse.targetX = e.touches[0].clientX;
                this.mouse.targetY = e.touches[0].clientY;
            }
        }, { passive: true });
    }
    
    initParticles() {
        this.particles = [];
        for (let i = 0; i < this.numParticles; i++) {
            this.particles.push(this.createParticle(true));
        }
    }
    
    createParticle(randomizeZ = false) {
        // Starfield spans -width to width, -height to height
        let w = window.innerWidth * 2.5;
        let h = window.innerHeight * 2.5;
        return {
            x: (Math.random() - 0.5) * w,
            y: (Math.random() - 0.5) * h,
            // Start depth further back or random
            z: randomizeZ ? Math.random() * 2000 : 2000,
            baseSpeed: Math.random() * 1.5 + 0.5,
            color: this.colors[Math.floor(Math.random() * this.colors.length)],
            radius: Math.random() * 1.5 + 0.5,
            angle: Math.random() * Math.PI * 2 // For ambient drift
        };
    }
    
    animate() {
        // Smooth mouse easing
        let dx = this.mouse.targetX - this.mouse.x;
        let dy = this.mouse.targetY - this.mouse.y;
        this.mouse.x += dx * 0.05; // easing
        this.mouse.y += dy * 0.05;
        
        let mouseSpeed = Math.sqrt(dx*dx + dy*dy);
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        for (let i = 0; i < this.particles.length; i++) {
            let p = this.particles[i];
            
            // Move particle towards camera (decrease z)
            // Dynamic speed increase if mouse is moving faster (depth effect)
            let speedMultiplier = this.mouse.moving ? (1 + Math.min(mouseSpeed * 0.03, 2.5)) : 1;
            p.z -= p.baseSpeed * speedMultiplier;
            
            // Slow ambient orbit/drift
            p.angle += 0.001;
            p.x += Math.cos(p.angle) * 0.5;
            p.y += Math.sin(p.angle) * 0.5;
            
            // Reset particle if it goes past the camera or too far away
            if (p.z <= 10) {
                Object.assign(p, this.createParticle(false));
                continue;
            }
            
            // Project 3D coordinate to 2D screen
            // The magic happens here: shifting the focal point to the mouse
            let fov = 350; // field of view factor
            let scale = fov / p.z;
            
            // The center of projection is tied to the smoothed mouse position
            let screenX = this.mouse.x + p.x * scale;
            let screenY = this.mouse.y + p.y * scale;
            
            // Size based on depth
            let size = p.radius * scale;
            if (size < 0.1) continue;
            
            // Opacity logic:
            // Fade in from distance, fade out when getting very close
            let opacity = 1;
            if (p.z > 1500) {
                opacity = 1 - ((p.z - 1500) / 500); // fade in 2000 -> 1500
            } else if (p.z < 300) {
                opacity = p.z / 300; // fade out 300 -> 0
            }
            
            // Slight repulsion and glow near the cursor
            let distToMouseX = screenX - this.mouse.targetX;
            let distToMouseY = screenY - this.mouse.targetY;
            let distToMouse = Math.sqrt(distToMouseX*distToMouseX + distToMouseY*distToMouseY);
            
            if (distToMouse < 150) {
                let repelForce = (150 - distToMouse) / 150;
                screenX += (distToMouseX / distToMouse) * repelForce * 15 * scale;
                screenY += (distToMouseY / distToMouse) * repelForce * 15 * scale;
                // Add a bright spot glow
                opacity = Math.min(1, opacity + repelForce * 0.6);
                size += repelForce * 1.5; // swell up when near mouse
            }
            
            // Draw the particle
            this.ctx.beginPath();
            this.ctx.arc(screenX, screenY, size, 0, Math.PI * 2);
            this.ctx.fillStyle = p.color;
            this.ctx.globalAlpha = Math.max(0, opacity);
            this.ctx.fill();
        }
        
        // Loop using requestAnimationFrame for GPU-friendly smooth rendering
        requestAnimationFrame(() => this.animate());
    }
}

// Instantiate the particle system once the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ParticleSystem();
});
