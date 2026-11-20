## D5: Energy Load Balancing
Welcome to the Physical AI Implementation of the D5: Energy Load Balancing project.

The D5: Energy Load Balancing project is a priority encoding system that operates on an LED strip and 2 small fans from a low voltage supply, abiding by a power budget. The priority optimization reads as follows: 

- Priority 1 (Ch 1 Essential Fan): Preserved at 100% unless hardware limit tripped.

- Priority 2 (Ch 2 Flexible Fan): Preserved ahead of decorative lighting; excludes unstable <25% duties.

- Priority 3 (Ch 3 LED Strip): Dimmed or shed first to stay within budget.

When set up physically, this project uses:

- GAO's 217030 BLE Gateway
  
- 3 BLE power measurement nodes
  
- 2 guarded cooling fans (DC 12V, PWM compatible)
  
- 1 dimmable LED strip (DC 12V)
  
- 3 PWM switching channels (4-ch MOSFET driver board, use 3 channels)
  
- 1 local station controller
  
- 1 operator load switch
  
- DC power supply (12V, 5A, 60W adapter)
  
- Customized 0.85m x 0.55m panel base
  
- 1 host PC (to run this program on)
  
- 1 ethernet router
  
- Any multimeter for testing
  
The following diagram is the project's directory structure:

```text
d5-energy-load-balancing/
├── docker-compose.yml               
├── mosquitto/
│   └── config/
│       └── mosquitto.conf          
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                  
│       ├── config.py                
│       ├── database.py              
│       ├── models.py               
│       ├── hal/
│       │   ├── base.py              
│       │   ├── gao_gateway.py       
│       │   ├── serial_controller.py 
│       │   └── synthetic.py
│       └── ai/
│           ├── forecaster.py        
│           └── optimizer.py         
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    └── src/
        └── app/
            ├── layout.tsx
            ├── globals.css
            └── page.tsx
```             
Using Python for the backend along with JavaScript, TypeScript, and CSS for the frontend, this program accurately simulates the D5 project's priority encoding system. The d5_backend, d5_frontend, d5_mosquitto, and d5_postgres all operate under Docker.

To run this program on any IDE:
1. Open Docker Desktop
2. Type the following commands into the terminal:
```text 
docker version --
docker compose up --build
```
If you have any questions regarding the development of this project, please feel free to reach out to me via Teams or E-Mail.

University E-Mail: aanwar08@uoguelph.ca

Personal E-Mail: alvinaianwar@gmail.com

## This project was implemented by Alvina Anwar.
