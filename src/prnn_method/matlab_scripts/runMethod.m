function [A, B, rs, xs, dt, gam, d, W, outputs] = runMethod(A, B, rs, xs, dt, gam, inputs, sym_eqs, verbose)
%% Initialize reservoir
rng(0);  
m = size(xs, 1);
RO = ReservoirTanhB(A,B,rs,xs,dt,gam);
d = RO.d;

%% Decompile RNN into dNPL
dv = A*rs + B*xs + d;
[Pd1,C1] = decomp_poly1_ns(A, B, rs, dv, 4);

% Compute shift matrix
[Pdx,Pdy] = find((sum(Pd1,2)+sum(Pd1,2)') <= max(sum(Pd1,2)));
PdS = zeros(size(Pd1,1));
for i = 1:length(Pdx)
    PdS(Pdx(i),Pdy(i)) = find(sum(Pd1==(Pd1(Pdx(i),:)+Pd1(Pdy(i),:)),2)==m);
end

%% Convert Symbolic Equations -- NEW
syms t; assume(t,'real'); 
syms x(t) [m,1]; x = x(t); assume(x,'real');

[output_eqs, recurrences, my_x] = eqs_py2mat(sym_eqs);
%% Shift && Compile
input_vector = sym(zeros(m, 1));
% generate input vector by checking for recurrences
for i = 1:length(recurrences)
    % get input & output #
    recurrence = recurrences{i};
    tokens = regexp(recurrence, 'o(\d+) == x(\d+)', 'tokens');
    if ~isempty(tokens)
        outputIndex = str2double(tokens{1}{1}); % o1 -> 1
        inputIndex = str2double(tokens{1}{2});  % x3 -> 3
    end

    % set recurrences to input vector
    input_vector(inputIndex) = 10 * output_eqs{outputIndex}; %TODO: why multiply by 10??
end

% Shift basis
pr = primes(2000)'; pr = pr(1:m);
[~,DX] = sym2deriv(input_vector,my_x,pr,Pd1,PdS);

% Finish generating basis
Aa  = zeros(size(C1));
Aa(:,(1:m)+1)  = Aa(:,(1:m)+1)+B;
Aa(:,1) = Aa(:,1) + d;
RdNPL = gen_basis(Aa,PdS);

% Compile
o = zeros(1,size(C1,2)); % Create the o matrix as zeros

%o(1,m+1) = 1; % set recurrent variables to one. Here, we take "1" x3 (see
%Pd1 for why)
oS = [];
for i = 1:length(recurrences)
    % get input & output #
    recurrence = recurrences{i};
    tokens = regexp(recurrence, 'o(\d+) == x(\d+)', 'tokens');
    if ~isempty(tokens)
        outputIndex = str2double(tokens{1}{1}); % o1 -> 1
        inputIndex = str2double(tokens{1}{2});  % x3 -> 3
    end
    o(1, 1 + inputIndex) = 1;
    oS = [oS; DX(inputIndex, :)];
end


%oS = DX(end,:); % indexing is a problem here! oS writes the terms from the symbolic equations in terms symbolic bases from Pd1
%oS = DX(1,:); % should be taking from all reccurent inputs.

OdNPL = o+oS/gam; % combines o and oS. Why divide by gam??
W = lsqminnorm(RdNPL', OdNPL')';

% Test for compilation accuracy
disp(['Compiler residual: ' num2str(norm(W*RdNPL - OdNPL))]);

%% Internalize recurrences -- NEW
reccA = A;
extB = B;
new_x = zeros(m, 1);
for i = 1:length(recurrences)
    % get input & output #
    recurrence = recurrences{i};
    tokens = regexp(recurrence, 'o(\d+) == x(\d+)', 'tokens');
    if ~isempty(tokens)
        outputIndex = str2double(tokens{1}{1}); % o1 -> 1
        inputIndex = str2double(tokens{1}{2});  % x3 -> 3
    end

    % internalize to adjacency/ splice B
    reccA = reccA + B(:, inputIndex)* W(outputIndex, :);

    if size(new_x, 1) == 1
        extB = zeros(size(extB, 1), 1);
        new_x = 0;
    else
        extB(:, inputIndex) = [];
        new_x(inputIndex) = [];
    end
    
end

RP = ReservoirTanhB(reccA,extB,rs, new_x,dt,gam);
RP.d = d;
A = reccA;
B = extB;
xs = new_x;


%% Run
pt = inputs;
rp = RP.train(pt);
wrp = W*rp;
outputs = wrp;

%% Plot
if 1
    time = 1:4000;
    figure;
    plot(time, pt(1, :, 1), 'DisplayName', 'Signal 1');
    hold on;
    plot(time, pt(2, :, 1), 'DisplayName', 'Signal 2');
    plot(time, outputs, 'DisplayName', 'outputs', 'LineWidth', 2);
    ylim([-.2 .2]);
    
    xlabel('Time');
    ylabel('Value');
    title('NAND Gate Signals and Output');
    legend;
    hold off;
end
end