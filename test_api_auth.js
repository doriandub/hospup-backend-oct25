// Simple test to simulate frontend API call
const API_BASE_URL = 'https://web-production-b52f.up.railway.app';

async function testAuth() {
    try {
        // Test health first
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        const healthData = await healthResponse.json();
        console.log('🟢 Health check:', healthData.status);
        
        // Try to get videos without auth (should fail)
        console.log('\n🔍 Testing videos API without auth...');
        const noAuthResponse = await fetch(`${API_BASE_URL}/api/v1/videos?video_type=uploaded`);
        const noAuthData = await noAuthResponse.json();
        console.log('❌ No auth result:', noAuthData.detail);
        
        // This simulates what the frontend does
        console.log('\n📋 Frontend will need to:');
        console.log('1. Get token from localStorage.getItem("access_token")');
        console.log('2. Set Authorization header: Bearer {token}');
        console.log('3. Make authenticated request to /api/v1/videos?video_type=uploaded');
        console.log('4. Filter results by property_id on client side');
        
    } catch (error) {
        console.error('❌ Test error:', error.message);
    }
}

testAuth();