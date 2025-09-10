// Simulate the exact frontend behavior
const API_BASE_URL = 'https://web-production-b52f.up.railway.app';
const COMPOSE_URL = 'https://hospup-frontend-2-kappa.vercel.app/dashboard/compose/c09678ad-e2eb-421d-88df-bfcb2dfd443d?property=2&prompt=Template%20choisi%20aléatoirement';

console.log('🧪 TESTING ASSET LIBRARY FIX');
console.log('==============================\n');

async function runTests() {
    // Test 1: Backend health
    console.log('1️⃣ Testing backend health...');
    try {
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        const healthData = await healthResponse.json();
        console.log(`   ✅ Backend: ${healthData.status}`);
        console.log(`   📊 Database: ${healthData.components.database.status} (${healthData.components.database.latency_ms}ms)`);
    } catch (error) {
        console.log(`   ❌ Backend health failed: ${error.message}`);
        return;
    }

    // Test 2: Frontend accessibility 
    console.log('\n2️⃣ Testing frontend deployment...');
    try {
        const frontendResponse = await fetch(COMPOSE_URL, { method: 'HEAD' });
        console.log(`   ✅ Frontend: HTTP ${frontendResponse.status}`);
        console.log(`   🌐 Age: ${frontendResponse.headers.get('age')}s (0 = fresh deploy)`);
    } catch (error) {
        console.log(`   ❌ Frontend failed: ${error.message}`);
    }

    // Test 3: API endpoint structure
    console.log('\n3️⃣ Testing API endpoint (no auth expected)...');
    try {
        const apiResponse = await fetch(`${API_BASE_URL}/api/v1/videos?property_id=2&status=uploaded,ready,completed`);
        const apiData = await apiResponse.json();
        
        if (apiResponse.status === 401 && apiData.detail?.includes('Not authenticated')) {
            console.log('   ✅ API endpoint working (auth required as expected)');
            console.log('   🔐 Authentication will be handled by browser with localStorage token');
        } else {
            console.log(`   ⚠️ Unexpected response: ${apiResponse.status} - ${apiData.detail}`);
        }
    } catch (error) {
        console.log(`   ❌ API test failed: ${error.message}`);
    }

    console.log('\n🎯 EXPECTED BEHAVIOR:');
    console.log('- User logs in → token stored in localStorage');
    console.log('- Page loads → api.get() called with Authorization header');
    console.log('- API responds with videos for property 2');
    console.log('- Assets Library populates with video cards');
    console.log('- Smart matching becomes available');
    
    console.log('\n📋 NEXT STEPS:');
    console.log('1. Open browser console on compose page');
    console.log('2. Look for "📚 Direct Assets-style API response:" logs');
    console.log('3. Look for "🎬 Assets-style Videos updated:" logs');
    console.log('4. Check if Assets Library shows videos');
    
    console.log(`\n🔗 Test URL: ${COMPOSE_URL}`);
}

runTests();