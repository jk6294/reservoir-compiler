% Problem parameters
m = 3;                      % Number: inputs (1 for feedback, 2 for signal)
n = 30;                     % Neurons per logic gate
% Reservoir parameters
dt = 0.001;
gam = 100;
A = sparse(zeros(n));       % Initial RNN connectivity
B = (rand(n,m)-.5)*.05;     % Input matrix
rs = (rand(n,1)-.5);
xs = zeros(m,1);

% generate inputs
ot = ones(2,1000,4);
pt_logic = cat(2,[-.1;-.1].*ot,[-.1;.1].*ot,[.1;-.1].*ot,[.1;.1].*ot);

%eqs = {'o1 == -123.076923076923*o1.^3 + 0.230769230769231*o1 + 5.0*(s1 + 0.1).*(-s2 - 0.1) + 0.1'};
nand_eq = {
    'o1 == -123.076923076923*o1.^3 + 0.230769230769231*o1 + 5.0*(s1 + 0.1).*(-s2 - 0.1) + 0.1'
};


pt_lorenz = zeros(1, 1000, 4);
verbose = false;
[A, B, rs, xs, dt, gam, d, W, outputs] = runMethod(A, B, rs, xs, dt, gam, pt_logic, nand_eq, verbose);

nand_res = ReservoirTanhB(A, B , rs, xs, dt, gam);

%% Plot
if 0
    time = 1:4000;
    figure;
    plot(time, pt_logic(1, :, 1), 'DisplayName', 'Signal 1');
    hold on;
    plot(time, pt_logic(2, :, 1), 'DisplayName', 'Signal 2');
    plot(time, outputs, 'DisplayName', 'outputs', 'LineWidth', 2);
    ylim([-.2 .2]);
    
    xlabel('Time');
    ylabel('Value');
    title('NAND Gate Signals and Output');
    legend;
    hold off;
end

% Oscillator
O = zeros(n); OB = zeros(n,1);
b1 = B(:,1);
b2 = B(:,2);
%b3 = B(:,3);

AC = [A             O             (b1+b2)*W;...
      (b1+b2)*W     A             O           ;...
      O             (b1+b2)*W     A         ];

BC = repmat(OB,[3,1]);

% Predict
RAD = ReservoirTanhB(AC,BC,repmat(rs,[3,1]),0,dt,gam);
RAD.d = repmat(d,[3,1]); 
RAD.r = repmat(rs,[3,1]);

time = 7000;
radp = RAD.train(zeros(1,time,4));

Wradp3 = [
    W*radp((1:n),:);    % readout, first nand
    W*radp((1:n)+n,:);  % readout, second nand
    W*radp((1:n)+2*n,:) % readout, third nand

];  

Wradp3(:,end); 
transformed_out = Wradp3(3, :);

%% Plot
if 1
    t_axis = 1:time;
    figure;
    plot(t_axis, transformed_out);
    
    xlabel('Time');
    ylabel('Value');
    title('Oscillator');
    legend;
    hold off;
end



