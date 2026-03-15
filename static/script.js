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
            n_posts: parseInt(document.getElementById('n_posts').value, 10)
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
            
            if (data.posts && data.posts.length > 0) {
                data.posts.forEach((post, index) => {
                    const delay = index * 0.1; // Stagger animation
                    
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
                            <div class="post-title">#${index + 1}: ${post.title || 'Post'}</div>
                            <div class="post-format">${post.format_hint || 'General'}</div>
                        </div>
                        <div class="post-content">${bodyContent.replace(/\n/g, '<br>')}</div>
                    `;
                    
                    postsContainer.appendChild(el);
                });
            } else {
                postsContainer.innerHTML = '<p>No posts returned.</p>';
            }
            
        } catch (error) {
            errorMsg.textContent = error.message;
            errorMsg.style.display = 'block';
        } finally {
            // Restore UI
            btnText.style.display = 'block';
            loader.style.display = 'none';
            submitBtn.disabled = false;
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
