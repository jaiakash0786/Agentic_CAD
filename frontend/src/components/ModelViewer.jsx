import { useEffect, useRef, Suspense } from 'react';
import { Canvas, useLoader, useThree } from '@react-three/fiber';
import { OrbitControls, Center, Environment } from '@react-three/drei';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import * as THREE from 'three';

function STLModel({ url, wireframe }) {
  const geometry = useLoader(STLLoader, url);
  const { camera } = useThree();

  useEffect(() => {
    if (geometry) {
      geometry.computeBoundingBox();
      const box = geometry.boundingBox;
      const center = new THREE.Vector3();
      box.getCenter(center);
      geometry.translate(-center.x, -center.y, -center.z);
      const size = new THREE.Vector3();
      box.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      camera.position.set(maxDim * 1.5, maxDim * 1.0, maxDim * 1.5);
      camera.updateProjectionMatrix();
    }
  }, [geometry, camera]);

  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial
        color="#8b5cf6"
        metalness={0.3}
        roughness={0.4}
        wireframe={wireframe}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

function EmptyScene() {
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={0.5} color="#8b5cf6" />
      {/* Grid helper */}
      <gridHelper args={[100, 20, '#1e293b', '#1e293b']} position={[0, -20, 0]} />
    </>
  );
}

export default function ModelViewer({ stlUrl, label }) {
  const [wireframe, setWireframe] = [false, () => {}]; // will lift state if needed

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'var(--bg-base)' }}>
      <Canvas
        camera={{ position: [150, 100, 150], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <color attach="background" args={['#0a0e1a']} />
        <ambientLight intensity={0.4} />
        <directionalLight position={[100, 100, 100]} intensity={0.8} />
        <directionalLight position={[-100, 50, -100]} intensity={0.3} color="#06b6d4" />
        <pointLight position={[0, 100, 0]} intensity={0.5} color="#8b5cf6" />

        {stlUrl ? (
          <Suspense fallback={null}>
            <Center>
              <STLModel url={stlUrl} wireframe={false} />
            </Center>
          </Suspense>
        ) : (
          <EmptyScene />
        )}

        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          rotateSpeed={0.8}
          zoomSpeed={1.2}
          minDistance={10}
          maxDistance={2000}
        />

        {/* Soft grid */}
        <gridHelper args={[500, 50, '#1e293b', '#1e293b']} position={[0, -80, 0]} />
      </Canvas>

      {/* Toolbar overlay */}
      <div className="viewer-toolbar">
        <span className="badge badge-purple" style={{ fontSize: '10px' }}>
          Three.js
        </span>
      </div>

      {/* Bottom label */}
      {label && (
        <div className="viewer-label">{label}</div>
      )}

      {/* Empty state */}
      {!stlUrl && (
        <div className="viewer-empty">
          <svg className="viewer-empty-icon" width="64" height="64" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="1" color="var(--accent-purple)">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <div style={{ fontSize: '13px', fontWeight: 600 }}>No model loaded</div>
          <div style={{ fontSize: '11px' }}>Run the pipeline to generate a 3D model</div>
        </div>
      )}
    </div>
  );
}
